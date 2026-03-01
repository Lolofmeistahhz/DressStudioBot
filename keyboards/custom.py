from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def custom_type_kb(types: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=t["name"], callback_data=f"cpt:{t['id']}")]
        for t in types
    ]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="custom:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def custom_colors_kb(colors: list[dict], type_id: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for i, c in enumerate(colors):
        row.append(InlineKeyboardButton(
            text=c["color"]["name"],
            callback_data=f"ccolor:{type_id}:{c['color']['id']}",
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ К типам", callback_data="custom:types")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def custom_sizes_kb(sizes: list[dict], type_id: int, color_id: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for s in sizes:
        row.append(InlineKeyboardButton(
            text=s["label"],
            callback_data=f"csize:{type_id}:{color_id}:{s['label']}",
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(
        text="◀️ К цветам",
        callback_data=f"cpt:{type_id}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def embroidery_source_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Выбрать из каталога", callback_data="cemb:catalog")],
        [InlineKeyboardButton(text="📷 Загрузить своё фото", callback_data="cemb:custom")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="custom:back_to_size")],
    ])


def prints_kb(prints: list[dict], page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:
    start = page * page_size
    chunk = prints[start:start + page_size]
    buttons = [
        [InlineKeyboardButton(text=p["name"], callback_data=f"cprint:{p['id']}")]
        for p in chunk
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"cprints_page:{page-1}"))
    if start + page_size < len(prints):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"cprints_page:{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cemb:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def print_sizes_kb(sizes: list[dict], print_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{s['label']} — {s['price']} ₽",
            callback_data=f"cpsize:{print_id}:{s['id']}",
        )]
        for s in sizes
    ]
    buttons.append([InlineKeyboardButton(text="◀️ К принтам", callback_data="cemb:catalog")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def custom_photos_kb(has_photos: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_photos:
        buttons.append([InlineKeyboardButton(text="➡️ Продолжить", callback_data="cphotos:done")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cemb:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def custom_confirm_kb(has_comment: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if not has_comment:
        buttons.append([InlineKeyboardButton(text="💬 Добавить комментарий", callback_data="custom:add_comment")])
    buttons.append([InlineKeyboardButton(text="✅ Отправить заявку", callback_data="custom:confirm")])
    buttons.append([InlineKeyboardButton(text="◀️ Отмена", callback_data="custom:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)