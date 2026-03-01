from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

READY_STATUS = {
    "pending_payment": "⏳ Ожидает оплаты",
    "paid":            "✅ Оплачен",
    "assembling":      "📦 Комплектуется",
    "shipped":         "🚚 Отправлен",
    "done":            "✅ Получен",
    "cancelled":       "❌ Отменён",
}

CUSTOM_STATUS = {
    "new":       "📝 Заявка отправлена",
    "reviewing": "👀 На рассмотрении",
    "accepted":  "✅ Принят — ожидает оплаты",
    "paid":      "💳 Оплачен — в работе",
    "in_work":   "🧵 Выполняется",
    "done":      "✅ Готов",
    "cancelled": "❌ Отменён",
}


def orders_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Заказы мерча",        callback_data="orders:ready")],
        [InlineKeyboardButton(text="🧵 Кастомные заказы",    callback_data="orders:custom")],
    ])


def orders_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="orders:menu")],
    ])


def order_pay_kb(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=url)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="orders:ready")],
    ])