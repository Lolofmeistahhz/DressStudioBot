"""
handlers/catalog.py

Флоу готового мерча:
  1. pt:{id}                       — список моделей (ТЕКСТ, без фото)
  2. pname:{type_id}:{idx}         — фото модели из ready_products + кнопка «Выбрать цвет»
  3. color_screen:{type_id}:{idx}  — color_palette_url + кнопки цветов (с ✗)
  4. color:{type_id}:{color_id}    — size_chart_url + кнопки размеров (с ✗)
  5. size:{type_id}:{color_id}:{l} — image_url товара + «В корзину»

FSM (CatalogFSM.browsing) хранит:
  type_id, names, name_idx, product_name, available_color_ids, color_id

Баг с доступностью (всегда ✗):
  Исправлено — available_color_ids берётся из /names и корректно передаётся
  в colors_kb. При запросе товаров фильтруем по name.
"""
import asyncio
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from handlers.utils import safe_answer, fetch_image, send_photo_or_text, to_text
from keyboards.catalog import (
    product_types_kb, product_names_kb, model_detail_kb,
    colors_kb, sizes_kb, add_to_cart_kb, after_add_kb,
    cart_kb, confirm_order_kb, payment_kb,
)
from keyboards.main import main_menu
from services import api

router = Router()
logger = logging.getLogger(__name__)


class CatalogFSM(StatesGroup):
    browsing = State()


# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

def _size_table_text(sizes: list[dict]) -> str:
    has_waist = any(s.get("waist_width") for s in sizes)
    header = "Р-р  | Дл  | Шир" + (" | Пояс" if has_waist else "") + " | Рук | Пл"
    rows   = [header, "─" * len(header)]
    for s in sizes:
        avail = "✓" if s.get("_available") else "✗"
        row   = f"{s['label']:4} {avail}| {s.get('length','—'):3} | {s.get('width','—'):3}"
        if has_waist:
            row += f" | {s.get('waist_width','—'):4}"
        row += f" | {s.get('sleeve','—'):3} | {s.get('shoulders','—')}"
        rows.append(row)
    return "\n".join(rows)


async def _get_fsm(state: FSMContext) -> dict:
    return await state.get_data()


# ─────────────────────────────────────────────────────────────────────────────
# Вход в каталог
# ─────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "🛍 Каталог")
async def show_catalog(message: Message, state: FSMContext):
    await state.clear()
    types = await api.get_product_types()
    if not types:
        await message.answer("😔 Каталог пока пуст.")
        return
    await message.answer("🛍 <b>Каталог</b>\n\nВыберите тип изделия:", reply_markup=product_types_kb(types))


@router.callback_query(F.data == "catalog:back")
async def cb_catalog_back(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Главное меню", reply_markup=main_menu)


@router.callback_query(F.data == "catalog:types")
async def cb_catalog_types(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    await state.clear()
    types = await api.get_product_types()
    if not types:
        return
    await to_text(callback, "🛍 <b>Каталог</b>\n\nВыберите тип изделия:", product_types_kb(types))


# ─────────────────────────────────────────────────────────────────────────────
# Шаг 1: Тип → список моделей (ТОЛЬКО ТЕКСТ, без фото)
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pt:"))
async def cb_product_type(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    type_id = int(callback.data.split(":")[1])

    pt, names = await asyncio.gather(
        api.get_product_type(type_id),
        api.get_product_names(type_id),
    )

    if not pt:
        await callback.message.answer("❌ Тип изделия не найден")
        return
    if not names:
        await callback.message.answer("😔 Нет доступных моделей.")
        return

    # Сохраняем контекст
    await state.set_state(CatalogFSM.browsing)
    await state.update_data(type_id=type_id, type_name=pt["name"], names=names)

    avail_count = sum(1 for n in names if n.get("available_color_ids"))
    text = (
        f"<b>{pt['name']}</b>\n"
        + (f"Состав: {pt['composition']}\n" if pt.get("composition") else "")
        + f"Цена: от <b>{pt['base_price']} ₽</b>\n"
        + (f"\n{pt['description']}\n" if pt.get("description") else "")
        + f"\nДоступно моделей: <b>{avail_count} из {len(names)}</b>\n\n"
        f"Выберите модель:"
    )

    # Только текст — без фото
    await to_text(callback, text, product_names_kb(names, type_id))


# ─────────────────────────────────────────────────────────────────────────────
# Шаг 2: Модель → фото изделия + кнопка «Выбрать цвет»
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pname:"))
async def cb_product_name(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    parts   = callback.data.split(":")
    type_id = int(parts[1])
    idx     = int(parts[2])

    data  = await _get_fsm(state)
    names = data.get("names")

    # Если FSM протух — восстанавливаем
    if not names:
        pt, names = await asyncio.gather(
            api.get_product_type(type_id),
            api.get_product_names(type_id),
        )
        if not names:
            await callback.message.answer("❌ Не удалось загрузить модели")
            return
        await state.set_state(CatalogFSM.browsing)
        await state.update_data(type_id=type_id, type_name=pt["name"] if pt else "", names=names)

    if idx >= len(names):
        await callback.message.answer("❌ Модель не найдена")
        return

    chosen       = names[idx]
    product_name = chosen["name"]
    avail_ids    = set(chosen.get("available_color_ids", []))

    await state.update_data(name_idx=idx, product_name=product_name, available_color_ids=list(avail_ids))

    # Берём фото первого доступного товара с этим названием
    products = await api.get_ready_products(product_type_id=type_id, name=product_name)
    # Сначала ищем с фото и в наличии, потом просто с фото
    image_url = None
    if products:
        with_photo_instock = [p for p in products if p.get("image_url") and p.get("stock_quantity", 0) > 0]
        with_photo         = [p for p in products if p.get("image_url")]
        best = with_photo_instock or with_photo
        if best:
            image_url = best[0]["image_url"]

    min_price = min((p["price"] for p in products), default=None) if products else None
    data2     = await _get_fsm(state)
    type_name = data2.get("type_name", "")

    has_stock = bool(avail_ids)
    stock_note = "" if has_stock else "\n⚠️ <b>Нет в наличии</b> — доступен кастомный заказ"
    price_str  = f"от <b>{min_price} ₽</b>" if min_price else "по запросу"

    text = (
        f"<b>{type_name}</b> · {product_name}\n"
        f"Цена: {price_str}{stock_note}\n\n"
        f"Выберите цвет для просмотра наличия:"
    )

    kb = model_detail_kb(type_id, idx)
    await send_photo_or_text(callback, image_url, text, kb)


# ─────────────────────────────────────────────────────────────────────────────
# Шаг 3: Экран выбора цвета → color_palette_url + кнопки цветов
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("color_screen:"))
async def cb_color_screen(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    parts   = callback.data.split(":")
    type_id = int(parts[1])
    idx     = int(parts[2])

    data  = await _get_fsm(state)
    names = data.get("names")

    # Восстанавливаем FSM если нужно
    if not names:
        pt, names = await asyncio.gather(
            api.get_product_type(type_id),
            api.get_product_names(type_id),
        )
        if not names or idx >= len(names):
            await callback.message.answer("❌ Не удалось загрузить данные")
            return
        await state.set_state(CatalogFSM.browsing)
        await state.update_data(type_id=type_id, type_name=pt["name"] if pt else "", names=names)
        data = await _get_fsm(state)

    if idx >= len(names):
        await callback.message.answer("❌ Модель не найдена")
        return

    chosen       = names[idx]
    product_name = chosen["name"]
    avail_ids    = set(chosen.get("available_color_ids", []))
    await state.update_data(name_idx=idx, product_name=product_name, available_color_ids=list(avail_ids))

    pt, colors = await asyncio.gather(
        api.get_product_type(type_id),
        api.get_type_colors(type_id),
    )
    if not pt or not colors:
        await callback.message.answer("❌ Не удалось загрузить цвета")
        return

    avail_count = len(avail_ids)
    text = (
        f"<b>{pt['name']}</b> · {product_name}\n\n"
        f"В наличии цветов: <b>{avail_count}</b>\n"
        f"✗ — нет на складе\n\n"
        f"Выберите цвет:"
    )
    kb = colors_kb(colors, type_id, idx, avail_ids)
    await send_photo_or_text(callback, pt.get("color_palette_url"), text, kb)


# ─────────────────────────────────────────────────────────────────────────────
# Шаг 4: Цвет → экран выбора размера → size_chart_url + кнопки размеров
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("color:"))
async def cb_color(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    _, type_id_s, color_id_s = callback.data.split(":")
    type_id, color_id = int(type_id_s), int(color_id_s)

    data = await _get_fsm(state)
    product_name = data.get("product_name")
    name_idx     = data.get("name_idx", 0)

    # Восстанавливаем product_name если FSM протух
    if not product_name:
        names = await api.get_product_names(type_id)
        if names and name_idx < len(names):
            product_name = names[name_idx]["name"]
            await state.update_data(product_name=product_name, names=names)

    pt, sizes, colors, products = await asyncio.gather(
        api.get_product_type(type_id),
        api.get_type_sizes(type_id),
        api.get_type_colors(type_id),
        # Фильтруем по name — это ключевой фикс бага с доступностью
        api.get_ready_products(product_type_id=type_id, color_id=color_id, name=product_name),
    )

    if not pt or not sizes:
        await callback.message.answer("❌ Не удалось загрузить данные")
        return

    # Доступные размеры для ЭТОЙ модели + ЭТОГО цвета
    available_labels: set[str] = {
        p["size_label"] for p in (products or []) if p["stock_quantity"] > 0
    }
    for s in sizes:
        s["_available"] = s["label"] in available_labels

    await state.update_data(color_id=color_id)

    color_name = next(
        (c["color"]["name"] for c in (colors or []) if c["color"]["id"] == color_id), ""
    )

    avail_str   = ", ".join(s["label"] for s in sizes if s.get("_available"))
    unavail_str = ", ".join(s["label"] for s in sizes if not s.get("_available"))
    stock_note  = (
        "✓ — в наличии  ✗ — нет на складе"
        if available_labels
        else "⚠️ <b>Этот цвет в этой модели отсутствует</b>"
    )

    name_line = f" · {product_name}" if product_name else ""
    parts = [f"<b>{pt['name']}</b>{name_line} · {color_name}"]
    if avail_str:
        parts.append(f"\n✅ В наличии: <b>{avail_str}</b>")
    if unavail_str:
        parts.append(f"❌ Нет: {unavail_str}")
    parts.append(f"\n{stock_note}\n\nВыберите размер:")
    caption = "\n".join(parts)

    kb = sizes_kb(sizes, type_id, color_id, available_labels, name_idx)

    photo = await fetch_image(pt.get("size_chart_url"))
    if photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=kb)
    else:
        text = (
            f"<b>{pt['name']}</b>{name_line} · {color_name}\n\n"
            f"<code>{_size_table_text(sizes)}</code>\n\n"
            f"{stock_note}\n\nВыберите размер:"
        )
        await to_text(callback, text, kb)


@router.callback_query(F.data.startswith("size_na:"))
async def cb_size_not_available(callback: CallbackQuery):
    size = callback.data.split(":")[1]
    await safe_answer(callback, f"Размер {size} сейчас отсутствует.\nОформите кастомный заказ 🧵", show_alert=True)


# ─────────────────────────────────────────────────────────────────────────────
# Шаг 5: Размер → карточка товара с фото
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("size:"))
async def cb_size(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    _, type_id_s, color_id_s, size_label = callback.data.split(":")
    type_id, color_id = int(type_id_s), int(color_id_s)

    data         = await _get_fsm(state)
    product_name = data.get("product_name")
    name_idx     = data.get("name_idx", 0)

    products, pt = await asyncio.gather(
        api.get_ready_products(product_type_id=type_id, color_id=color_id, name=product_name),
        api.get_product_type(type_id),
    )
    if not pt:
        return

    product    = next((p for p in (products or []) if p["size_label"] == size_label), None)
    color_name = product["color"]["name"] if product else ""

    if not product or product["stock_quantity"] == 0:
        await safe_answer(callback, f"Размер {size_label} только что закончился 😔", show_alert=True)
        return

    name_line = f"\nМодель: <b>{product_name}</b>" if product_name else ""
    text = (
        f"<b>{pt['name']}</b>{name_line}\n"
        f"Цвет: <b>{color_name}</b> · Размер: <b>{size_label}</b>\n"
        f"Цена: <b>{product['price']} ₽</b>\n"
        f"На складе: {product['stock_quantity']} шт.\n\n"
        f"Добавить в корзину?"
    )
    await send_photo_or_text(
        callback, product.get("image_url"), text,
        add_to_cart_kb(product["id"], type_id, color_id, name_idx),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Корзина
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cart_add:"))
async def cb_add_to_cart(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    parts = callback.data.split(":")
    product_id, type_id, color_id = int(parts[1]), int(parts[2]), int(parts[3])

    user = await api.get_user(callback.from_user.id)
    if not user or not user.get("delivery_complete"):
        await callback.message.answer("⚠️ Сначала заполните данные доставки в разделе «Профиль»")
        return

    cart = await api.add_to_cart(callback.from_user.id, product_id)
    if not cart:
        await callback.message.answer("❌ Не удалось добавить в корзину")
        return

    data     = await _get_fsm(state)
    name_idx = data.get("name_idx", 0)

    text = (
        f"✅ <b>Добавлено в корзину!</b>\n\n"
        f"В корзине: {cart['items_count']} поз. на <b>{cart['total']} ₽</b>\n\nЧто дальше?"
    )
    kb = after_add_kb(type_id, name_idx)
    if callback.message.photo:
        try:
            await callback.message.edit_caption(caption=text, reply_markup=kb)
        except Exception:
            await callback.message.answer(text, reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except Exception:
            await callback.message.answer(text, reply_markup=kb)


def _cart_text(cart: dict) -> str:
    lines = ["🛒 <b>Корзина</b>\n"]
    for item in cart["items"]:
        p        = item["ready_product"]
        name_str = f" ({p['name']})" if p.get("name") else ""
        lines.append(
            f"• {p['product_type']['name']}{name_str} {p['color']['name']} р.{p['size_label']}"
            f" × {item['quantity']} = <b>{item['subtotal']} ₽</b>"
        )
    lines.append(f"\n💰 Итого: <b>{cart['total']} ₽</b>")
    return "\n".join(lines)


@router.message(F.text == "🛒 Корзина")
async def show_cart(message: Message):
    cart = await api.get_cart(message.from_user.id)
    if not cart or not cart.get("items"):
        await message.answer("🛒 Корзина пуста", reply_markup=cart_kb(False))
        return
    await message.answer(_cart_text(cart), reply_markup=cart_kb(True))


@router.callback_query(F.data == "cart:view")
async def cb_cart_view(callback: CallbackQuery):
    await safe_answer(callback)
    cart = await api.get_cart(callback.from_user.id)
    has  = bool(cart and cart.get("items"))
    await to_text(callback, _cart_text(cart) if has else "🛒 Корзина пуста", cart_kb(has))


@router.callback_query(F.data.startswith("cart_qty:"))
async def cb_cart_qty(callback: CallbackQuery):
    await safe_answer(callback)
    _, item_id_s, delta_s = callback.data.split(":")
    item_id, delta = int(item_id_s), int(delta_s)
    cart = await api.get_cart(callback.from_user.id)
    if not cart:
        return
    item = next((i for i in cart["items"] if i["id"] == item_id), None)
    if not item:
        return
    new_qty = item["quantity"] + delta
    result  = (
        await api.remove_cart_item(callback.from_user.id, item_id)
        if new_qty <= 0
        else await api.update_cart_item(callback.from_user.id, item_id, new_qty)
    )
    if not result:
        return
    has = bool(result.get("items"))
    await to_text(callback, _cart_text(result) if has else "🛒 Корзина пуста", cart_kb(has))


@router.callback_query(F.data.startswith("cart_rm:"))
async def cb_cart_remove(callback: CallbackQuery):
    await safe_answer(callback, "Удалено")
    result = await api.remove_cart_item(callback.from_user.id, int(callback.data.split(":")[1]))
    if not result:
        return
    has = bool(result.get("items"))
    await to_text(callback, _cart_text(result) if has else "🛒 Корзина пуста", cart_kb(has))


@router.callback_query(F.data == "cart:clear")
async def cb_cart_clear(callback: CallbackQuery):
    await safe_answer(callback)
    await api.clear_cart(callback.from_user.id)
    await to_text(callback, "🛒 Корзина очищена", cart_kb(False))


@router.callback_query(F.data == "cart:checkout")
async def cb_checkout(callback: CallbackQuery):
    await safe_answer(callback)
    user = await api.get_user(callback.from_user.id)
    if not user or not user.get("delivery_complete"):
        await callback.message.answer("⚠️ Заполните данные доставки в профиле")
        return
    cart = await api.get_cart(callback.from_user.id)
    if not cart or not cart.get("items"):
        return
    carrier_map = {"cdek": "СДЭК", "yandex": "Яндекс Доставка"}
    text = (
        f"{_cart_text(cart)}\n\n<b>📦 Доставка:</b>\n"
        f"Получатель: {user['delivery_name']}\n"
        f"Телефон: {user['phone']}\n"
        f"Город: {user['delivery_city']}\n"
        f"Адрес: {user['delivery_address']}\n"
        f"Перевозчик: {carrier_map.get(user.get('delivery_carrier') or '', '—')}\n\n"
        f"Подтверждаете заказ?"
    )
    await to_text(callback, text, confirm_order_kb())


@router.callback_query(F.data == "order:confirm")
async def cb_order_confirm(callback: CallbackQuery):
    await safe_answer(callback)
    await to_text(callback, "⏳ Оформляем заказ...", None)
    order = await api.create_ready_order(callback.from_user.id)
    if not order:
        await callback.message.edit_text("❌ Не удалось создать заказ. Попробуйте позже.")
        return
    await callback.message.edit_text("⏳ Создаём ссылку на оплату...")
    payment = await api.create_payment("ready_order", order["id"], float(order["total_price"]))
    if not payment:
        await callback.message.edit_text(
            f"✅ Заказ <b>№{order['id']}</b> создан!\n"
            f"Сумма: <b>{order['total_price']} ₽</b>\n\n"
            f"⚠️ Не удалось создать ссылку. Зайдите в «Мои заказы».",
        )
        return
    await callback.message.edit_text(
        f"✅ Заказ <b>№{order['id']}</b> создан!\n"
        f"Сумма: <b>{order['total_price']} ₽</b>\n\nНажмите кнопку для оплаты:",
        reply_markup=payment_kb(payment["confirmation_url"]),
    )