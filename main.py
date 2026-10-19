import flet as ft
import sqlite3
import csv
import os
import random
import string
from datetime import datetime

# Database setup
DB_NAME = "passwords.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL DEFAULT 'عمومی',
            title TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT
        )
    """)
    # Migration: check if category column exists for older databases
    cursor.execute("PRAGMA table_info(accounts)")
    columns = [row[1] for row in cursor.fetchall()]
    if "category" not in columns:
        cursor.execute("ALTER TABLE accounts ADD COLUMN category TEXT DEFAULT 'عمومی'")
    conn.commit()
    conn.close()

def add_account(category, title, username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute(
        "INSERT INTO accounts (category, title, username, password, created_at) VALUES (?, ?, ?, ?, ?)",
        (category, title, username, password, now)
    )
    conn.commit()
    conn.close()

def get_grouped_accounts(search=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if search:
        cursor.execute(
            """SELECT id, category, title, username, password, created_at 
               FROM accounts 
               WHERE category LIKE ? OR title LIKE ? OR username LIKE ? 
               ORDER BY category ASC, id DESC""",
            (f"%{search}%", f"%{search}%", f"%{search}%")
        )
    else:
        cursor.execute(
            "SELECT id, category, title, username, password, created_at FROM accounts ORDER BY category ASC, id DESC"
        )
    rows = cursor.fetchall()
    conn.close()

    # Group by category
    grouped = {}
    for r in rows:
        cat = r[1] if r[1] else "عمومی"
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(r)
    return grouped

def delete_account(account_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()

def export_to_csv():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, category, title, username, password, created_at FROM accounts ORDER BY id DESC")
    records = cursor.fetchall()
    conn.close()

    filename = f"passwords_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.abspath(filename)
    with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Category / Group", "Title / Account", "Username / Email", "Password", "Date Created"])
        for r in records:
            writer.writerow(r)
    return filepath

# Password generator logic
def generate_password(length=12, use_upper=True, use_lower=True, use_digits=True, use_symbols=True):
    pool = ""
    if use_upper:
        pool += string.ascii_uppercase
    if use_lower:
        pool += string.ascii_lowercase
    if use_digits:
        pool += string.digits
    if use_symbols:
        pool += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not pool:
        pool = string.ascii_letters + string.digits

    return "".join(random.choice(pool) for _ in range(int(length)))

# Compatible Button Widget
ButtonWidget = getattr(ft, "FilledButton", getattr(ft, "ElevatedButton", ft.Button))

def main(page: ft.Page):
    page.title = "مدیریت رمزها | Password Manager"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 15

    try:
        if hasattr(page, "window") and page.window is not None:
            page.window.width = 440
            page.window.height = 780
            page.window.resizable = True
    except Exception:
        pass

    init_db()

    # Notification Helper
    def show_snack(text, color=ft.Colors.GREEN_400):
        snack = ft.SnackBar(content=ft.Text(text, color=ft.Colors.WHITE), bgcolor=color)
        if hasattr(page, "show_dialog"):
            page.show_dialog(snack)
        elif hasattr(page, "overlay"):
            snack.open = True
            page.overlay.append(snack)
            page.update()

    # Clipboard Helper
    def copy_text(text, label="متن"):
        try:
            if hasattr(page, "set_clipboard"):
                page.set_clipboard(text)
            elif hasattr(ft, "Clipboard") and hasattr(page, "run_task"):
                page.run_task(ft.Clipboard().set, text)
        except Exception:
            pass
        show_snack(f"{label} در کلیپ‌بورد کپی شد!", ft.Colors.BLUE_600)

    # Dialog Helpers
    def open_dialog(dlg):
        if hasattr(page, "show_dialog"):
            page.show_dialog(dlg)
        else:
            page.dialog = dlg
            dlg.open = True
            page.update()

    def close_dialog(dlg=None):
        if hasattr(page, "pop_dialog"):
            page.pop_dialog()
        elif dlg:
            dlg.open = False
            page.update()

    # Form inputs
    category_input = ft.TextField(
        label="دسته / سرویس (مثلاً Google یا Instagram)",
        prefix_icon=ft.Icons.FOLDER_OUTLINED,
        border_radius=10,
        text_size=14,
    )
    title_input = ft.TextField(
        label="عنوان حساب (مثلاً ایمیل اصلی یا اکانت دوم)",
        prefix_icon=ft.Icons.LABEL_OUTLINED,
        border_radius=10,
        text_size=14,
    )
    user_input = ft.TextField(
        label="نام کاربری / ایمیل",
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        border_radius=10,
        text_size=14,
    )
    pass_input = ft.TextField(
        label="رمز عبور",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        border_radius=10,
        text_size=14,
        expand=True,
    )

    search_input = ft.TextField(
        hint_text="جستجو در دسته‌ها، عناوین یا یوزرها...",
        prefix_icon=ft.Icons.SEARCH,
        border_radius=10,
        text_size=13,
        expand=True,
    )

    items_list = ft.ListView(expand=True, spacing=10, padding=5)

    # Confirm Delete Dialog
    def confirm_delete_dialog(aid, title):
        def proceed_delete(e):
            delete_account(aid)
            close_dialog(dlg)
            refresh_list()
            show_snack(f"رمز '{title}' با موفقیت حذف شد", ft.Colors.RED_600)

        def cancel_delete(e):
            close_dialog(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text("تایید حذف رمز", weight=ft.FontWeight.BOLD),
            content=ft.Text(f"آیا از حذف حساب «{title}» اطمینان دارید؟ این عملیات قابل بازگشت نیست."),
            actions=[
                ft.TextButton("انصراف", on_click=cancel_delete),
                ft.TextButton("بله، حذف کن", style=ft.ButtonStyle(color=ft.Colors.RED_400), on_click=proceed_delete),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(dlg)

    # Advanced Password Generator Dialog
    def open_password_generator(e=None):
        length_slider = ft.Slider(min=4, max=32, value=14, divisions=28, label="{value} کاراکتر")
        length_text = ft.Text("طول رمز: 14", size=13, weight=ft.FontWeight.BOLD)
        cb_upper = ft.Checkbox(label="حروف بزرگ (A-Z)", value=True)
        cb_lower = ft.Checkbox(label="حروف کوچک (a-z)", value=True)
        cb_digits = ft.Checkbox(label="اعداد (0-9)", value=True)
        cb_symbols = ft.Checkbox(label="نمادهای خاص (!@#$...)", value=True)

        preview_text = ft.Text(
            generate_password(14, True, True, True, True),
            size=16,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.LIGHT_GREEN_400,
            selectable=True,
            expand=True,
        )

        def update_generated_pass(ev=None):
            length_text.value = f"طول رمز: {int(length_slider.value)}"
            new_pass = generate_password(
                int(length_slider.value),
                cb_upper.value,
                cb_lower.value,
                cb_digits.value,
                cb_symbols.value,
            )
            preview_text.value = new_pass
            gen_dlg.update()

        length_slider.on_change = update_generated_pass
        cb_upper.on_change = update_generated_pass
        cb_lower.on_change = update_generated_pass
        cb_digits.on_change = update_generated_pass
        cb_symbols.on_change = update_generated_pass

        def apply_password(ev):
            pass_input.value = preview_text.value
            pass_input.update()
            close_dialog(gen_dlg)
            show_snack("رمز عبور جدید در فرم قرار گرفت!")

        def copy_generated(ev):
            copy_text(preview_text.value, "رمز تولید شده")

        gen_dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.KEY_OUTLINED, color=ft.Colors.AMBER_400),
                ft.Text("تولید رمز عبور پیشرفته", size=17, weight=ft.FontWeight.BOLD),
            ]),
            content=ft.Container(
                width=380,
                content=ft.Column(
                    [
                        ft.Container(
                            padding=12,
                            border_radius=8,
                            bgcolor=getattr(ft.Colors, "BLACK_54", getattr(ft.Colors, "BLACK54", "black54")),
                            content=ft.Row(
                                [
                                    preview_text,
                                    ft.IconButton(
                                        icon=ft.Icons.REFRESH,
                                        tooltip="تولید مجدد",
                                        on_click=update_generated_pass,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.COPY,
                                        tooltip="کپی این رمز",
                                        on_click=copy_generated,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                        ),
                        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                        length_text,
                        length_slider,
                        cb_upper,
                        cb_lower,
                        cb_digits,
                        cb_symbols,
                    ],
                    tight=True,
                    spacing=6,
                ),
            ),
            actions=[
                ft.TextButton("بستن", on_click=lambda _: close_dialog(gen_dlg)),
                ButtonWidget("استفاده از این رمز", icon=ft.Icons.CHECK, on_click=apply_password),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(gen_dlg)

    # Refresh list and group by category
    def refresh_list(e=None):
        items_list.controls.clear()
        query = search_input.value or ""
        grouped = get_grouped_accounts(query)

        if not grouped:
            items_list.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.LOCK_OPEN, size=50, color=ft.Colors.GREY_500),
                            ft.Text("هیچ رمزی ذخیره نشده است", color=ft.Colors.GREY_400, size=14),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    alignment=ft.Alignment(0, 0),
                    padding=40,
                )
            )
        else:
            for cat_name, accounts in grouped.items():
                def set_quick_cat(cn=cat_name):
                    category_input.value = cn
                    category_input.focus()
                    page.update()
                    show_snack(f"دسته '{cn}' برای افزودن آیتم انتخاب شد", ft.Colors.BLUE_700)

                cat_cards = []
                for acc in accounts:
                    acc_id, cat, title, username, password, created_at = acc

                    card = ft.Card(
                        elevation=2,
                        content=ft.Container(
                            padding=10,
                            border_radius=8,
                            bgcolor=ft.Colors.GREY_900,
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Row([
                                                ft.Icon(ft.Icons.VPN_KEY_OUTLINED, color=ft.Colors.AMBER_400, size=18),
                                                ft.Text(title, weight=ft.FontWeight.BOLD, size=15),
                                            ]),
                                            ft.IconButton(
                                                icon=ft.Icons.DELETE_OUTLINE,
                                                icon_color=ft.Colors.RED_400,
                                                icon_size=20,
                                                tooltip="حذف حساب",
                                                on_click=lambda _, aid=acc_id, t=title: confirm_delete_dialog(aid, t),
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    # Username row with Copy
                                    ft.Row(
                                        [
                                            ft.Row([
                                                ft.Icon(ft.Icons.PERSON, size=16, color=ft.Colors.GREY_400),
                                                ft.Text(f"{username}", size=13, color=ft.Colors.GREY_300, selectable=True),
                                            ]),
                                            ft.IconButton(
                                                icon=ft.Icons.COPY,
                                                icon_size=16,
                                                tooltip="کپی نام کاربری",
                                                on_click=lambda _, u=username: copy_text(u, "نام کاربری"),
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    # Password row with Copy
                                    ft.Row(
                                        [
                                            ft.Row([
                                                ft.Icon(ft.Icons.KEY, size=16, color=ft.Colors.GREY_400),
                                                ft.Text(f"{password}", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.LIGHT_GREEN_400, selectable=True),
                                            ]),
                                            ft.IconButton(
                                                icon=ft.Icons.COPY,
                                                icon_size=16,
                                                tooltip="کپی رمز عبور",
                                                on_click=lambda _, p=password: copy_text(p, "رمز عبور"),
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Text(f"تاریخ: {created_at}", size=10, color=ft.Colors.GREY_600),
                                ],
                                spacing=4,
                            ),
                        ),
                    )
                    cat_cards.append(card)

                # ExpansionTile for Category
                expansion_tile = ft.ExpansionTile(
                    title=ft.Row([
                        ft.Icon(ft.Icons.FOLDER, color=ft.Colors.BLUE_400, size=20),
                        ft.Text(cat_name, weight=ft.FontWeight.BOLD, size=16),
                        ft.Container(
                            content=ft.Text(f"{len(accounts)} مورد", size=11, color=ft.Colors.GREY_400),
                            padding=ft.Padding.symmetric(horizontal=8, vertical=2) if hasattr(ft, "Padding") else 5,
                            border_radius=10,
                            bgcolor=getattr(ft.Colors, "BLACK_45", getattr(ft.Colors, "BLACK45", "black45")),
                        ),
                    ], spacing=8),
                    trailing=ft.IconButton(
                        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                        icon_color=ft.Colors.GREEN_400,
                        tooltip=f"افزودن آیتم جدید به {cat_name}",
                        on_click=lambda _, cn=cat_name: set_quick_cat(cn),
                    ),
                    expanded=True,
                    controls=cat_cards,
                )
                items_list.controls.append(expansion_tile)

        page.update()

    # Save handler
    def handle_save(e):
        cat = category_input.value.strip() or "عمومی"
        t = title_input.value.strip()
        u = user_input.value.strip() or "-"
        p = pass_input.value.strip()

        if not t or not p:
            show_snack("لطفاً حداقل عنوان و رمز عبور را وارد کنید!", ft.Colors.ORANGE_800)
            return

        add_account(cat, t, u, p)
        title_input.value = ""
        user_input.value = ""
        pass_input.value = ""
        refresh_list()
        show_snack(f"رمز با موفقیت در دسته '{cat}' ذخیره شد!")

    # Export CSV handler
    def handle_export(e):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM accounts")
        count = c.fetchone()[0]
        conn.close()

        if count == 0:
            show_snack("هیچ رمزی برای خروجی گرفتن وجود ندارد!", ft.Colors.ORANGE_700)
            return
        try:
            csv_path = export_to_csv()
            show_snack(f"فایل CSV ایجاد شد:\n{os.path.basename(csv_path)}")
        except Exception as ex:
            show_snack(f"خطا در ایجاد CSV: {ex}", ft.Colors.RED_600)

    search_input.on_change = refresh_list

    # Header layout
    header = ft.Row(
        [
            ft.Row([
                ft.Icon(ft.Icons.SHIELD_ROUNDED, size=28, color=ft.Colors.BLUE_400),
                ft.Text("Password Keeper", size=19, weight=ft.FontWeight.BOLD),
            ]),
            ft.Row([
                ft.IconButton(
                    icon=ft.Icons.KEY_OUTLINED,
                    icon_color=ft.Colors.AMBER_400,
                    tooltip="تولیدکننده رمز عبور پیشرفته",
                    on_click=open_password_generator,
                ),
                ft.IconButton(
                    icon=ft.Icons.FILE_DOWNLOAD,
                    icon_color=ft.Colors.GREEN_400,
                    tooltip="دریافت فایل CSV (اکسپورت)",
                    on_click=handle_export,
                ),
            ]),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    # Input form box
    pass_row = ft.Row(
        [
            pass_input,
            ft.IconButton(
                icon=ft.Icons.CASINO_OUTLINED,
                icon_color=ft.Colors.AMBER_400,
                tooltip="تولید رمز رندوم پیشرفته",
                on_click=open_password_generator,
            ),
        ],
        spacing=0,
    )

    input_box = ft.Container(
        padding=12,
        border_radius=12,
        bgcolor=ft.Colors.GREY_900,
        content=ft.Column(
            [
                category_input,
                title_input,
                user_input,
                pass_row,
                ButtonWidget(
                    "ذخیره رمز جدید",
                    icon=ft.Icons.ADD,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.BLUE_700,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    width=420,
                    on_click=handle_save,
                ),
            ],
            spacing=8,
        ),
    )

    search_bar = ft.Row([search_input], alignment=ft.MainAxisAlignment.CENTER)

    page.add(
        header,
        ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
        input_box,
        ft.Divider(height=10, color=ft.Colors.GREY_800),
        search_bar,
        items_list,
    )

    refresh_list()

if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
