import flet as ft
import pymysql
import pymysql.cursors
import traceback
import os

# ---------- ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ----------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "br4zkrmg44zjff6yerpy-mysql.services.clever-cloud.com"),
    "user": os.getenv("DB_USER", "ufdjphz9dcpjotfm"),
    "password": os.getenv("DB_PASSWORD", "zVqWHfoWbHmh1NaZQ5x6"),
    "database": os.getenv("DB_NAME", "br4zkrmg44zjff6yerpy"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "cursorclass": pymysql.cursors.DictCursor
}

cart = []
all_products = []
selected_category = "Все"
sort_by = "name_asc"
search_query = ""
cart_dialog = None

def get_connection():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        raise

def ensure_tables():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE 'products'")
        if not cursor.fetchone():
            print("Таблица products не найдена, создаём структуру...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code CHAR(6) NOT NULL UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    category VARCHAR(100) NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    quantity INT NOT NULL DEFAULT 0,
                    brand VARCHAR(100) NOT NULL,
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_number INT NOT NULL UNIQUE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sellers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    seller_number INT NOT NULL UNIQUE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_id INT NOT NULL,
                    seller_id INT NOT NULL,
                    product_id INT NOT NULL,
                    quantity INT NOT NULL,
                    price_at_moment DECIMAL(10,2) NOT NULL,
                    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(id),
                    FOREIGN KEY (seller_id) REFERENCES sellers(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            """)
            conn.commit()
            print("Таблицы созданы (пустые).")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")
        traceback.print_exc()

def main(page: ft.Page):
    page.title = "PC Parts Store"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 8
    page.scroll = ft.ScrollMode.AUTO

    try:
        ensure_tables()
    except Exception as e:
        page.add(ft.Text(f"Ошибка инициализации БД: {e}", size=18, color=ft.Colors.RED))
        page.update()
        return

    progress_bar = ft.ProgressBar(visible=False, color=ft.Colors.BLUE, height=4)

    products_grid = ft.GridView(
        expand=True,
        runs_count=2,
        spacing=6,
        run_spacing=6,
        padding=4,
        child_aspect_ratio=1.2
    )

    seller = ft.TextField(
        label="Seller",
        width=90,
        keyboard_type=ft.KeyboardType.NUMBER,
        value="1",
        dense=True,
        text_size=12,
        height=36,
        input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]*", replacement_string="")
    )

    product_count_label = ft.Text("Товаров: 0", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700)

    search_field = ft.TextField(
        label="Поиск по названию или бренду",
        prefix_icon=ft.Icons.SEARCH,
        on_change=lambda e: update_search(e.control.value),
        dense=True,
        height=40
    )

    def update_search(query):
        global search_query
        if len(query) > 100:
            query = query[:100]
            search_field.value = query
            page.update()
        search_query = query.strip()
        apply_filters_and_sort()

    def notify(msg, color=ft.Colors.GREEN):
        sb = ft.SnackBar(content=ft.Text(msg, size=14), bgcolor=color, duration=2000)
        page.overlay.append(sb)
        sb.open = True
        page.update()

    # Бейдж корзины (вручную)
    cart_badge = ft.Container(
        content=ft.Text("0", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        bgcolor=ft.Colors.RED, border_radius=10, width=20, height=20,
        alignment=ft.Alignment(0, 0), right=0, top=0, visible=False
    )

    def update_cart_badge():
        total_items = sum(item["quantity"] for item in cart)
        cart_badge.content = ft.Text(str(total_items), size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        cart_badge.visible = total_items > 0
        page.update()

    def apply_filters_and_sort():
        filtered = all_products
        if selected_category != "Все":
            filtered = [p for p in filtered if p["category"] == selected_category]
        if search_query:
            q = search_query.lower()
            filtered = [p for p in filtered if q in p["name"].lower() or q in p["brand"].lower()]
        if sort_by == "price_asc":
            filtered.sort(key=lambda x: float(x["price"]))
        elif sort_by == "price_desc":
            filtered.sort(key=lambda x: float(x["price"]), reverse=True)
        elif sort_by == "name_asc":
            filtered.sort(key=lambda x: x["name"].lower())
        elif sort_by == "name_desc":
            filtered.sort(key=lambda x: x["name"].lower(), reverse=True)
        display_products(filtered)

    def display_products(products):
        products_grid.controls.clear()
        if not products:
            products_grid.controls.append(
                ft.Container(
                    content=ft.Text("Товары не найдены", size=16),
                    alignment=ft.Alignment(0, 0),
                    expand=True
                )
            )
        else:
            for p in products:
                price = float(p["price"])
                qty = int(p["quantity"])
                in_stock = qty > 0
                products_grid.controls.append(
                    ft.Card(
                        elevation=2,
                        content=ft.Container(
                            padding=4,
                            content=ft.Column([
                                ft.Text(p["name"], size=12, weight=ft.FontWeight.BOLD, max_lines=2),
                                ft.Text(p["category"], size=10, opacity=0.6),
                                ft.Text(f"Бренд: {p['brand']}", size=10, opacity=0.5),
                                ft.Text(f"{price:.0f} ₽", size=13, weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.GREEN_700),
                                ft.Text(f"В наличии: {qty} шт.", size=10,
                                        color=ft.Colors.GREY_600 if in_stock else ft.Colors.RED),
                                ft.Button(
                                    content=ft.Text("+", color=ft.Colors.WHITE),
                                    on_click=lambda e, x=p: add_to_cart(x) if x["quantity"] > 0 else None,
                                    width=36,
                                    height=26,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=5),
                                        padding=2
                                    ),
                                    bgcolor=ft.Colors.BLUE_700 if in_stock else ft.Colors.GREY_400,
                                    disabled=not in_stock
                                )
                            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                        )
                    )
                )
        product_count_label.value = f"Товаров: {len(products)}"
        page.update()

    def load_products():
        global all_products, categories
        progress_bar.visible = True
        page.update()
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT code, name, category, price, quantity, brand, description
                FROM products
                WHERE is_active = 1
                ORDER BY name
            """)
            all_products = cursor.fetchall()
            for p in all_products:
                p["price"] = float(p["price"])
                p["quantity"] = int(p["quantity"])
            print(f"Загружено товаров из БД: {len(all_products)}")
            cats = set(p['category'] for p in all_products if p['category'])
            categories = ["Все"] + sorted(cats)
            category_chips.controls = [
                ft.Chip(
                    label=ft.Text(cat, size=11,
                                  color=ft.Colors.BLUE_700 if cat == selected_category else ft.Colors.GREY_800,
                                  weight=ft.FontWeight.BOLD if cat == selected_category else ft.FontWeight.NORMAL),
                    selected=cat == selected_category,
                    on_click=lambda e, c=cat: set_category(c),
                    bgcolor=ft.Colors.BLUE_50 if cat == selected_category else ft.Colors.TRANSPARENT,
                    padding=2
                )
                for cat in categories
            ]
            apply_filters_and_sort()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Ошибка загрузки товаров: {e}")
            traceback.print_exc()
            notify(f"Ошибка загрузки товаров: {e}", ft.Colors.RED)
        finally:
            progress_bar.visible = False
            page.update()

    def add_to_cart(p):
        code = p["code"]
        name = p["name"]
        price = float(p["price"])
        for item in cart:
            if item["code"] == code:
                item["quantity"] += 1
                update_cart_badge()
                notify(f"{name} x{item['quantity']}")
                return
        cart.append({"code": code, "name": name, "price": price, "quantity": 1})
        update_cart_badge()
        notify(f"{name} добавлен")

    def close_cart_dialog():
        global cart_dialog
        if cart_dialog:
            try:
                page.close(cart_dialog)
            except AttributeError:
                cart_dialog.open = False
                page.update()
            cart_dialog = None

    def close_all_dialogs():
        close_cart_dialog()
        for control in page.overlay[:]:
            if isinstance(control, ft.AlertDialog):
                try:
                    page.close(control)
                except AttributeError:
                    control.open = False
                    try:
                        page.overlay.remove(control)
                    except:
                        pass
        page.update()

    # ---------- КОРЗИНА ----------
    def build_cart_content():
        content = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8, expand=True)
        total_price = 0.0
        for item in cart:
            total_price += item["price"] * item["quantity"]
            content.controls.append(
                ft.Row([
                    ft.Column([
                        ft.Text(item["name"], size=13, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{item['price']:.0f} ₽ x {item['quantity']} = {item['price'] * item['quantity']:.0f} ₽", size=11)
                    ], expand=True, spacing=2),
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        icon_color=ft.Colors.BLUE,
                        on_click=lambda e, code=item["code"]: change_qty(code, 1)
                    ),
                    ft.Text(str(item["quantity"]), size=14, weight=ft.FontWeight.BOLD),
                    ft.IconButton(
                        icon=ft.Icons.REMOVE,
                        icon_color=ft.Colors.BLUE,
                        on_click=lambda e, code=item["code"]: change_qty(code, -1)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE,
                        icon_color=ft.Colors.RED,
                        on_click=lambda e, code=item["code"]: remove_item(code)
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            )
        content.controls.append(ft.Divider(height=5))
        content.controls.append(ft.Text(f"Итого: {total_price:,.2f} ₽", size=16, weight=ft.FontWeight.BOLD))
        content.controls.append(
            ft.Row([
                ft.Button(
                    content=ft.Text("Очистить корзину", color=ft.Colors.WHITE),
                    on_click=lambda e: clear_cart(),
                    bgcolor=ft.Colors.RED_700,
                    expand=True,
                    height=40,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
                ),
                ft.Button(
                    content=ft.Text("Оформить заказ", color=ft.Colors.WHITE),
                    on_click=place_order,
                    bgcolor=ft.Colors.GREEN_700,
                    expand=True,
                    height=40,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
                )
            ], spacing=10)
        )
        return content

    def show_cart_dialog(e=None):
        global cart_dialog
        close_cart_dialog()
        if not cart:
            notify("Корзина пуста", ft.Colors.ORANGE)
            return

        content = build_cart_content()

        title_row = ft.Row([
            ft.Text("Корзина", size=20, weight=ft.FontWeight.BOLD),
            ft.IconButton(
                icon=ft.Icons.CLOSE,
                on_click=lambda e: close_cart_dialog(),
                icon_color=ft.Colors.GREY_700
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        cart_dialog = ft.AlertDialog(
            modal=True,
            title=title_row,
            content=ft.Container(
                content=content,
                width=min(page.width * 0.92, 900),
                height=min(page.height * 0.8, 700),
                padding=15
            )
        )
        try:
            page.open(cart_dialog)
        except AttributeError:
            page.overlay.append(cart_dialog)
            cart_dialog.open = True
        page.update()

    def update_cart_dialog():
        show_cart_dialog()

    def change_qty(code, delta):
        for item in cart[:]:
            if item["code"] == code:
                item["quantity"] += delta
                if item["quantity"] <= 0:
                    cart.remove(item)
                break
        update_cart_badge()
        if not cart:
            close_cart_dialog()
            notify("Корзина пуста", ft.Colors.ORANGE)
        else:
            update_cart_dialog()

    def remove_item(code):
        cart[:] = [item for item in cart if item["code"] != code]
        update_cart_badge()
        if not cart:
            close_cart_dialog()
            notify("Корзина пуста", ft.Colors.ORANGE)
        else:
            update_cart_dialog()

    def clear_cart():
        cart.clear()
        update_cart_badge()
        close_cart_dialog()
        notify("Корзина очищена", ft.Colors.ORANGE)

    # ---------- ОФОРМЛЕНИЕ ЗАКАЗА ----------
    def place_order(e):
        if not cart:
            notify("Корзина пуста", ft.Colors.ORANGE)
            return

        seller_num_str = seller.value.strip()
        if not seller_num_str:
            notify("Введите номер продавца", ft.Colors.ORANGE)
            return

        if len(seller_num_str) > 5:
            notify("Номер продавца не может быть длиннее 5 цифр", ft.Colors.ORANGE)
            return

        try:
            seller_num = int(seller_num_str)
        except ValueError:
            notify("Номер продавца должен быть числом", ft.Colors.ORANGE)
            return

        if seller_num <= 0 or seller_num > 99999:
            notify("Номер продавца должен быть от 1 до 99999", ft.Colors.ORANGE)
            return

        progress_bar.visible = True
        page.update()
        try:
            conn = get_connection()
            cursor = conn.cursor()
            conn.begin()

            cursor.execute("SELECT id FROM customers WHERE customer_number=1")
            c = cursor.fetchone()
            if c:
                customer_id = c['id']
            else:
                cursor.execute("INSERT INTO customers(customer_number) VALUES (1)")
                customer_id = cursor.lastrowid

            cursor.execute("SELECT id FROM sellers WHERE seller_number=%s", (seller_num,))
            s = cursor.fetchone()
            if s:
                seller_id = s['id']
            else:
                cursor.execute("INSERT INTO sellers(seller_number) VALUES (%s)", (seller_num,))
                seller_id = cursor.lastrowid

            total = 0.0
            for item in cart:
                code = item["code"]
                qty = item["quantity"]
                cursor.execute("SELECT id, price, quantity FROM products WHERE code=%s AND is_active=1 FOR UPDATE", (code,))
                prod = cursor.fetchone()
                if not prod:
                    raise Exception(f"Товар {code} не найден")
                product_id = prod['id']
                price = float(prod['price'])
                stock = prod['quantity']
                if stock < qty:
                    raise Exception(f"Недостаточно товара {code} (доступно {stock})")
                cursor.execute("UPDATE products SET quantity = quantity - %s WHERE id=%s", (qty, product_id))
                cursor.execute("""
                    INSERT INTO orders (customer_id, seller_id, product_id, quantity, price_at_moment)
                    VALUES (%s, %s, %s, %s, %s)
                """, (customer_id, seller_id, product_id, qty, price))
                total += qty * price

            conn.commit()
            cart.clear()
            update_cart_badge()
            close_cart_dialog()
            notify(f"Заказ на {total:,.2f} ₽ принят!", ft.Colors.GREEN)
            load_products()
            cursor.close()
            conn.close()
        except Exception as ex:
            try:
                conn.rollback()
            except:
                pass
            notify(f"Ошибка: {ex}", ft.Colors.RED)
            print(f"Ошибка оформления заказа: {ex}")
            traceback.print_exc()
        finally:
            progress_bar.visible = False
            page.update()

    # ---------- ИСТОРИЯ ЗАКАЗОВ ----------
    def load_orders(e):
        close_cart_dialog()
        progress_bar.visible = True
        page.update()
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.name, o.quantity, o.price_at_moment, o.order_date,
                       (o.quantity * o.price_at_moment) AS total
                FROM orders o
                JOIN customers c ON c.id = o.customer_id
                JOIN products p ON p.id = o.product_id
                WHERE c.customer_number = 1
                ORDER BY o.order_date DESC
            """)
            data = cursor.fetchall()
            cursor.close()
            conn.close()
            if not data:
                notify("Нет заказов", ft.Colors.ORANGE)
                return

            history_content = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8)
            for o in data:
                try:
                    total = float(o["total"])
                except:
                    total = 0.0
                history_content.controls.append(
                    ft.Card(
                        content=ft.Container(
                            padding=8,
                            content=ft.Column([
                                ft.Text(o["name"], size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(f"{o['quantity']} шт. • {o['order_date']}", size=11, opacity=0.7),
                                ft.Text(f"{total:.0f} ₽", size=14, weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.GREEN_700)
                            ], spacing=2)
                        )
                    )
                )

            def close_history_dialog():
                try:
                    page.close(dialog)
                except:
                    dialog.open = False
                    page.update()

            title_row = ft.Row([
                ft.Text("История заказов", size=20, weight=ft.FontWeight.BOLD),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    on_click=lambda e: close_history_dialog(),
                    icon_color=ft.Colors.GREY_700
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

            dialog = ft.AlertDialog(
                modal=False,
                title=title_row,
                content=ft.Container(
                    content=history_content,
                    width=page.width * 0.9,
                    height=page.height * 0.8,
                    padding=10
                )
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()
        except Exception as e:
            notify(f"Ошибка загрузки истории: {e}", ft.Colors.RED)
            print(f"Ошибка истории: {e}")
            traceback.print_exc()
        finally:
            progress_bar.visible = False
            page.update()

    # ---------- СПРАВОЧНЫЙ ДИАЛОГ ----------
    def show_help_dialog(e):
        close_all_dialogs()

        about_program = ft.Column([
            ft.Text("О программе", size=18, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text(
                "Приложение для оформления заказов компьютерной техники.\n"
                "Версия: 2.0 (прямое подключение к БД)\n"
                "Разработано с использованием Python, Flet, MySQL."
            )
        ], spacing=10)

        about_dev = ft.Column([
            ft.Text("О разработчике", size=18, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text(
                "Разработчик: Фейлер Станислав Константинович\n"
                "Группа: ИС-943\n"
                "Проект: Практическая работа по программному модулю магазин комплектующих для ПК"
            )
        ], spacing=10)

        user_guide = ft.Column([
            ft.Text("Руководство пользователя", size=18, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text(
                "1. Выбор товара – нажмите «+» на карточке товара, чтобы добавить в корзину.\n"
                "2. Просмотр корзины – нажмите на иконку 🛒 в верхней панели.\n"
                "3. Оформление заказа – в корзине нажмите «Оформить заказ», номер продавца берётся из поля вверху.\n"
                "4. Очистка корзины – в корзине нажмите «Очистить корзину».\n"
                "5. Фильтрация по категориям – выберите категорию товара.\n"
                "6. Сортировка – используйте меню сортировки.\n"
                "7. Поиск – введите название или бренд в поле поиска.\n"
                "8. История заказов – нажмите на ⋮ и выберите «История заказов».\n"
                "9. Обновление товаров – кнопка 🔄 рядом с сортировкой.\n"
                "10. Номер продавца – только цифры от 1 до 99999."
            )
        ], spacing=10)

        display = ft.Container(content=about_program, padding=5, expand=True)

        def switch_tab(tab_index):
            if tab_index == 0:
                display.content = about_program
            elif tab_index == 1:
                display.content = about_dev
            else:
                display.content = user_guide
            page.update()

        tabs_row = ft.Row(
            [
                ft.TextButton("О программе", on_click=lambda e: switch_tab(0)),
                ft.TextButton("Разработчик", on_click=lambda e: switch_tab(1)),
                ft.TextButton("Руководство", on_click=lambda e: switch_tab(2)),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
        )

        def close_help_dialog():
            try:
                page.close(dialog)
            except:
                dialog.open = False
                page.update()

        title_row = ft.Row([
            ft.Text("Справочная информация", size=20, weight=ft.FontWeight.BOLD),
            ft.IconButton(
                icon=ft.Icons.CLOSE,
                on_click=lambda e: close_help_dialog(),
                icon_color=ft.Colors.GREY_700
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        dialog = ft.AlertDialog(
            modal=False,
            title=title_row,
            content=ft.Container(
                content=ft.Column([tabs_row, ft.Divider(), display]),
                width=page.width * 0.85,
                height=page.height * 0.7,
                padding=10
            )
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    # ---------- ИНТЕРФЕЙС (без логотипа) ----------
    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip="Обновить товары",
        on_click=lambda e: load_products(),
        icon_color=ft.Colors.BLUE_700
    )

    # Кнопка корзины с кастомным бейджем
    cart_btn = ft.TextButton(
        content=ft.Text("🛒", size=28, color=ft.Colors.BLUE_700),
        on_click=show_cart_dialog,
        style=ft.ButtonStyle(padding=4),
        tooltip="Корзина"
    )

    header = ft.Row([
        ft.Text("PC Parts Store", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
        ft.Row([
            seller,
            ft.Stack([cart_btn, cart_badge]),
            ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT,
                tooltip="Меню",
                items=[
                    ft.PopupMenuItem(content=ft.Text("📜 История заказов"), on_click=load_orders),
                    ft.PopupMenuItem(content=ft.Text("❓ Справка"), on_click=show_help_dialog),
                ]
            )
        ], spacing=8)
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    categories = ["Все"]
    category_chips = ft.Row(
        [
            ft.Chip(
                label=ft.Text(cat, size=11,
                              color=ft.Colors.BLUE_700 if cat == selected_category else ft.Colors.GREY_800,
                              weight=ft.FontWeight.BOLD if cat == selected_category else ft.FontWeight.NORMAL),
                selected=cat == selected_category,
                on_click=lambda e, c=cat: set_category(c),
                bgcolor=ft.Colors.BLUE_50 if cat == selected_category else ft.Colors.TRANSPARENT,
                padding=2
            )
            for cat in categories
        ],
        wrap=True, spacing=4, run_spacing=4
    )

    def set_category(cat):
        global selected_category
        selected_category = cat
        for chip in category_chips.controls:
            is_selected = chip.label.value == cat
            chip.selected = is_selected
            chip.bgcolor = ft.Colors.BLUE_50 if is_selected else ft.Colors.TRANSPARENT
            chip.label.color = ft.Colors.BLUE_700 if is_selected else ft.Colors.GREY_800
            chip.label.weight = ft.FontWeight.BOLD if is_selected else ft.FontWeight.NORMAL
        page.update()
        apply_filters_and_sort()

    def set_sort(sort_key):
        global sort_by
        sort_by = sort_key
        apply_filters_and_sort()

    sort_menu = ft.PopupMenuButton(
        icon="sort", tooltip="Сортировка",
        items=[
            ft.PopupMenuItem(content=ft.Text("По названию А-Я"), on_click=lambda e: set_sort("name_asc")),
            ft.PopupMenuItem(content=ft.Text("По названию Я-А"), on_click=lambda e: set_sort("name_desc")),
            ft.PopupMenuItem(content=ft.Text("Сначала дешевле"), on_click=lambda e: set_sort("price_asc")),
            ft.PopupMenuItem(content=ft.Text("Сначала дороже"), on_click=lambda e: set_sort("price_desc")),
        ],
    )

    main_content = ft.Column(
        expand=True,
        controls=[
            header,
            ft.Divider(height=5),
            ft.Row([ft.Text("Products", size=14, weight=ft.FontWeight.BOLD), refresh_btn, sort_menu],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            search_field,
            category_chips,
            progress_bar,
            products_grid,
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[product_count_label]
            )
        ],
        spacing=5
    )

    page.add(main_content)

    def page_resize(e):
        if page.width > 1000:
            products_grid.runs_count = 4
        elif page.width > 700:
            products_grid.runs_count = 3
        else:
            products_grid.runs_count = 2
        page.update()

    page.on_resize = page_resize

    load_products()
    update_cart_badge()

if __name__ == "__main__":
    ft.run(main)
