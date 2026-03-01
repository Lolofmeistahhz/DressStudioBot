from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def product_types_kb(types: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=t["name"], callback_data=f"pt:{t['id']}")]
        for t in types
    ]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="catalog:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def colors_kb(colors: list[dict], type_id: int) -> InlineKeyboardMarkup:
    """
    Кнопки цветов — название + наличие.
    Точный цвет показываем в подписи к фото (свотч генерируется в хендлере).
    """
    buttons = []
    row = []
    for c in colors:
        in_stock = c.get("in_stock", True)
        label = c["color"]["name"] if in_stock else f"{c['color']['name']} ✗"
        row.append(InlineKeyboardButton(
            text=label,
            callback_data=f"color:{type_id}:{c['color']['id']}",
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ К типам", callback_data="catalog:types")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sizes_kb(
    sizes: list[dict],
    type_id: int,
    color_id: int,
    available_labels: set[str] | None = None,
) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for s in sizes:
        label = s["label"]
        if available_labels is not None:
            if label in available_labels:
                btn_text, cb = label, f"size:{type_id}:{color_id}:{label}"
            else:
                btn_text, cb = f"{label} ✗", f"size_na:{label}"
        else:
            btn_text, cb = label, f"size:{type_id}:{color_id}:{label}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=cb))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ К цветам", callback_data=f"pt:{type_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def add_to_cart_kb(product_id: int, type_id: int, color_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data=f"cart_add:{product_id}:{type_id}:{color_id}")],
        [InlineKeyboardButton(text="◀️ К размерам", callback_data=f"color:{type_id}:{color_id}")],
    ])


def after_add_kb(type_id: int, color_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Перейти в корзину",   callback_data="cart:view")],
        [InlineKeyboardButton(text="🎨 Выбрать другой цвет", callback_data=f"pt:{type_id}")],
        [InlineKeyboardButton(text="🛍 К типам изделий",     callback_data="catalog:types")],
    ])


def cart_kb(has_items: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_items:
        buttons.append([InlineKeyboardButton(text="✅ Оформить заказ",  callback_data="cart:checkout")])
        buttons.append([InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="cart:clear")])
    buttons.append([InlineKeyboardButton(text="🛍 В каталог", callback_data="catalog:types")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_order_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и оплатить", callback_data="order:confirm")],
        [InlineKeyboardButton(text="◀️ Назад в корзину",        callback_data="cart:view")],
    ])


def payment_kb(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=url)],
    ])