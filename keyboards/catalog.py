"""
keyboards/catalog.py

Флоу:
  1. Типы        pt:{id}               → текст, без фото
  2. Модели      pname:{type_id}:{idx} → фото изделия из ready_products
  3. Цвета       color_screen:{type_id}:{name_idx} → color_palette_url
  4. Размеры     color:{type_id}:{color_id}        → size_chart_url
  5. Карточка    size:{type_id}:{color_id}:{label} → image_url товара
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def product_types_kb(types: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=t["name"], callback_data=f"pt:{t['id']}")] for t in types]
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="catalog:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_names_kb(names: list[dict], type_id: int) -> InlineKeyboardMarkup:
    """
    Список моделей внутри типа.
    ✗ если ни один цвет не в наличии для этой модели.
    """
    rows = []
    for i, n in enumerate(names):
        has_stock = bool(n.get("available_color_ids"))
        label = n["name"] if has_stock else f"{n['name']} ✗"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"pname:{type_id}:{i}")])
    rows.append([InlineKeyboardButton(text="◀️ К типам", callback_data="catalog:types")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def model_detail_kb(type_id: int, name_idx: int) -> InlineKeyboardMarkup:
    """Кнопки под фото конкретной модели."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Выбрать цвет", callback_data=f"color_screen:{type_id}:{name_idx}")],
        [InlineKeyboardButton(text="◀️ К моделям",    callback_data=f"pt:{type_id}")],
    ])


def colors_kb(
    colors: list[dict],
    type_id: int,
    name_idx: int,
    available_color_ids: set[int],
) -> InlineKeyboardMarkup:
    """
    Кнопки цветов. ✗ если нет в наличии для выбранной модели.
    """
    rows = []
    row  = []
    for c in colors:
        cid   = c["color"]["id"]
        label = c["color"]["name"]
        if cid not in available_color_ids:
            label = f"{label} ✗"
        row.append(InlineKeyboardButton(text=label, callback_data=f"color:{type_id}:{cid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(
        text="◀️ К модели",
        callback_data=f"color_screen:{type_id}:{name_idx}",   # назад к экрану фото модели
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sizes_kb(
    sizes: list[dict],
    type_id: int,
    color_id: int,
    available_labels: set[str],
    name_idx: int,
) -> InlineKeyboardMarkup:
    rows = []
    row  = []
    for s in sizes:
        label = s["label"]
        if label in available_labels:
            btn, cb = label, f"size:{type_id}:{color_id}:{label}"
        else:
            btn, cb = f"{label} ✗", f"size_na:{label}"
        row.append(InlineKeyboardButton(text=btn, callback_data=cb))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(
        text="◀️ К цветам",
        callback_data=f"color_screen:{type_id}:{name_idx}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def add_to_cart_kb(product_id: int, type_id: int, color_id: int, name_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data=f"cart_add:{product_id}:{type_id}:{color_id}")],
        [InlineKeyboardButton(text="◀️ К размерам",         callback_data=f"color:{type_id}:{color_id}")],
    ])


def after_add_kb(type_id: int, name_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Перейти в корзину",   callback_data="cart:view")],
        [InlineKeyboardButton(text="🎨 Выбрать другой цвет", callback_data=f"color_screen:{type_id}:{name_idx}")],
        [InlineKeyboardButton(text="🛍 К типам изделий",     callback_data="catalog:types")],
    ])


def cart_kb(has_items: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_items:
        rows.append([InlineKeyboardButton(text="✅ Оформить заказ",  callback_data="cart:checkout")])
        rows.append([InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="cart:clear")])
    rows.append([InlineKeyboardButton(text="🛍 В каталог", callback_data="catalog:types")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_order_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и оплатить", callback_data="order:confirm")],
        [InlineKeyboardButton(text="◀️ Назад в корзину",        callback_data="cart:view")],
    ])


def payment_kb(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=url)],
    ])