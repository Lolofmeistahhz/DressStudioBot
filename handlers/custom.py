"""
handlers/custom.py

Баг 3 fix: проверяем pt is not None перед обращением к полям
Баг 2 fix: корректная загрузка фото (BytesIO.read())
Картинки: color_palette_url на выборе цвета, size_chart_url на выборе размера
"""
import asyncio
import logging
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from handlers.utils import safe_answer, fetch_image, send_photo_or_text, to_text
from keyboards.custom import (
    custom_type_kb, custom_colors_kb, custom_sizes_kb,
    embroidery_source_kb, prints_kb, print_sizes_kb,
    custom_photos_kb, custom_confirm_kb,
)
from keyboards.main import main_menu
from services import api

router = Router()
logger = logging.getLogger(__name__)

MAX_PHOTOS = 5


class CustomFSM(StatesGroup):
    choosing_type       = State()
    choosing_color      = State()
    choosing_size       = State()
    choosing_embroidery = State()
    browsing_prints     = State()
    uploading_photos    = State()
    writing_comment     = State()
    confirming          = State()


@router.message(F.text == "🧵 Кастомный заказ")
async def start_custom(message: Message, state: FSMContext):
    await state.clear()
    user = await api.get_user(message.from_user.id)
    if not user or not user.get("delivery_complete"):
        await message.answer("⚠️ Для оформления заказа необходимо заполнить данные доставки в разделе «Профиль».")
        return
    types = await api.get_product_types()
    if not types:
        await message.answer("😔 Каталог изделий недоступен.")
        return
    await state.set_state(CustomFSM.choosing_type)
    await message.answer("🧵 <b>Кастомный заказ</b>\n\nВыберите тип изделия:", reply_markup=custom_type_kb(types))


@router.callback_query(F.data == "custom:back")
async def cb_custom_back(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Главное меню", reply_markup=main_menu)


@router.callback_query(F.data == "custom:cancel")
async def cb_custom_cancel(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    await state.clear()
    await to_text(callback, "❌ Заказ отменён.", None)


# ── Выбор типа (БАГ 3 FIX: проверяем pt is not None) ─────────────────────────

@router.callback_query(F.data.startswith("cpt:"))
async def cb_custom_type(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    type_id = int(callback.data.split(":")[1])

    pt, colors = await asyncio.gather(
        api.get_product_type(type_id),
        api.get_type_colors(type_id),
    )

    # БАГ 3: pt может быть None если API вернул ошибку
    if not pt:
        await callback.message.answer("❌ Не удалось загрузить тип изделия. Попробуйте позже.")
        return
    if not colors:
        await callback.message.answer("❌ Нет доступных цветов.")
        return

    await state.update_data(type_id=type_id, type_name=pt["name"])
    await state.set_state(CustomFSM.choosing_color)

    text = (
        f"<b>{pt['name']}</b>\n"
        + (f"Состав: {pt['composition']}\n" if pt.get("composition") else "")
        + f"Цена: от <b>{pt['base_price']} ₽</b>\n\nВыберите цвет:"
    )
    # Показываем палитру цветов
    await send_photo_or_text(callback, pt.get("color_palette_url"), text, custom_colors_kb(colors, type_id))


@router.callback_query(F.data == "custom:types")
async def cb_back_to_types(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    await state.set_state(CustomFSM.choosing_type)
    types = await api.get_product_types()
    await to_text(callback, "🧵 Выберите тип изделия:", custom_type_kb(types or []))


# ── Выбор цвета → размеры: показываем size_chart_url ─────────────────────────

@router.callback_query(F.data.startswith("ccolor:"))
async def cb_custom_color(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    _, type_id_s, color_id_s = callback.data.split(":")
    type_id, color_id = int(type_id_s), int(color_id_s)

    pt, sizes, colors = await asyncio.gather(
        api.get_product_type(type_id),
        api.get_type_sizes(type_id),
        api.get_type_colors(type_id),
    )

    if not pt or not sizes:
        await callback.message.answer("❌ Не удалось загрузить данные. Попробуйте позже.")
        return

    color_name = next(
        (c["color"]["name"] for c in (colors or []) if c["color"]["id"] == color_id), ""
    )
    await state.update_data(color_id=color_id, color_name=color_name)
    await state.set_state(CustomFSM.choosing_size)

    data = await state.get_data()
    kb   = custom_sizes_kb(sizes, type_id, color_id)

    caption = (
        f"<b>{data['type_name']}</b> · {color_name}\n\n"
        f"Все размеры в см, погрешность 1–2 см.\n\nВыберите размер:"
    )

    # Показываем размерную сетку
    size_chart_url = pt.get("size_chart_url")
    if size_chart_url:
        photo = await fetch_image(size_chart_url)
        if photo:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=kb)
            return

    # Нет картинки — текстовая таблица
    has_waist = any(s.get("waist_width") for s in sizes)
    header = "Р-р  | Дл  | Шир" + (" | Пояс" if has_waist else "") + " | Рук | Пл"
    rows   = [header, "─" * len(header)]
    for s in sizes:
        row = f"{s['label']:4}  | {s.get('length','—'):3} | {s.get('width','—'):3}"
        if has_waist:
            row += f" | {s.get('waist_width','—'):4}"
        row += f" | {s.get('sleeve','—'):3} | {s.get('shoulders','—')}"
        rows.append(row)

    text = (
        f"<b>{data['type_name']}</b> · {color_name}\n\n"
        f"<code>{chr(10).join(rows)}</code>\n\nВыберите размер:"
    )
    await send_photo_or_text(callback, None, text, kb)


# ── Выбор размера ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("csize:"))
async def cb_custom_size(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    _, type_id_s, color_id_s, size_label = callback.data.split(":")
    await state.update_data(size_label=size_label)
    await state.set_state(CustomFSM.choosing_embroidery)
    data = await state.get_data()
    text = (
        f"<b>{data['type_name']}</b> · {data['color_name']} · {size_label}\n\n"
        f"Откуда возьмём вышивку?"
    )
    await to_text(callback, text, embroidery_source_kb())


@router.callback_query(F.data == "custom:back_to_size")
async def cb_back_to_size(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    data  = await state.get_data()
    sizes = await api.get_type_sizes(data["type_id"])
    await state.set_state(CustomFSM.choosing_size)
    await to_text(callback, "Выберите размер:", custom_sizes_kb(sizes or [], data["type_id"], data["color_id"]))


# ── Источник вышивки ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "cemb:catalog")
async def cb_emb_catalog(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    prints = await api.get_prints()
    if not prints:
        await callback.message.answer("Каталог принтов пуст")
        return
    await state.update_data(all_prints=prints, prints_page=0)
    await state.set_state(CustomFSM.browsing_prints)
    await to_text(callback, "🖼 Выберите принт из каталога:", prints_kb(prints, page=0))


@router.callback_query(F.data.startswith("cprints_page:"))
async def cb_prints_page(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    page = int(callback.data.split(":")[1])
    data = await state.get_data()
    await state.update_data(prints_page=page)
    try:
        await callback.message.edit_reply_markup(reply_markup=prints_kb(data.get("all_prints", []), page=page))
    except Exception:
        pass


@router.callback_query(F.data.startswith("cprint:"))
async def cb_print_chosen(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    print_id = int(callback.data.split(":")[1])
    data     = await state.get_data()
    chosen   = next((p for p in data.get("all_prints", []) if p["id"] == print_id), None)
    if not chosen or not chosen.get("sizes"):
        await callback.message.answer("Нет доступных размеров для этого принта")
        return
    await state.update_data(print_id=print_id, print_name=chosen["name"])
    text = f"🖼 <b>{chosen['name']}</b>\n\nВыберите размер вышивки:"
    await send_photo_or_text(callback, chosen.get("image_url"), text, print_sizes_kb(chosen["sizes"], print_id))


@router.callback_query(F.data.startswith("cpsize:"))
async def cb_print_size_chosen(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    _, print_id_s, size_id_s = callback.data.split(":")
    print_id, size_id = int(print_id_s), int(size_id_s)
    data   = await state.get_data()
    chosen = next((p for p in data.get("all_prints", []) if p["id"] == print_id), None)
    size   = next((s for s in (chosen["sizes"] if chosen else []) if s["id"] == size_id), None)
    await state.update_data(print_size_id=size_id, print_size_label=size["label"] if size else "")
    await state.set_state(CustomFSM.confirming)
    await _show_custom_confirm(callback.message, state, is_photo=bool(callback.message.photo))


@router.callback_query(F.data == "cemb:custom")
async def cb_emb_custom(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    await state.update_data(custom_images=[], print_id=None, print_size_id=None)
    await state.set_state(CustomFSM.uploading_photos)
    await to_text(
        callback,
        "📷 Отправьте фото вышивки / референс (до 5 фото).\n\nКогда закончите — нажмите <b>«Продолжить»</b>.",
        custom_photos_kb(has_photos=False),
    )


@router.callback_query(F.data == "cemb:back")
async def cb_emb_back(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    data = await state.get_data()
    await state.set_state(CustomFSM.choosing_embroidery)
    await to_text(
        callback,
        f"<b>{data['type_name']}</b> · {data['color_name']} · {data['size_label']}\n\nОткуда возьмём вышивку?",
        embroidery_source_kb(),
    )


# ── Загрузка фото (БАГ 2 FIX) ────────────────────────────────────────────────

@router.message(CustomFSM.uploading_photos, F.photo)
async def handle_photo_upload(message: Message, state: FSMContext):
    data   = await state.get_data()
    images = data.get("custom_images", [])

    if len(images) >= MAX_PHOTOS:
        await message.answer(f"Максимум {MAX_PHOTOS} фото. Нажмите «Продолжить».")
        return

    photo = message.photo[-1]  # берём наибольшее разрешение
    file  = await message.bot.get_file(photo.file_id)

    # БАГ 2 FIX: download_file возвращает BytesIO, читаем байты явно
    file_io    = await message.bot.download_file(file.file_path)
    raw_bytes  = file_io.read() if hasattr(file_io, "read") else bytes(file_io)

    url = await api.upload_photo(raw_bytes, f"custom_{message.from_user.id}_{len(images)}.jpg")
    if not url:
        await message.answer("❌ Не удалось загрузить фото. Попробуйте ещё раз.")
        return

    images.append(url)
    await state.update_data(custom_images=images)
    await message.answer(
        f"✅ Фото {len(images)}/{MAX_PHOTOS} загружено.",
        reply_markup=custom_photos_kb(has_photos=True),
    )


@router.callback_query(F.data == "cphotos:done")
async def cb_photos_done(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    data = await state.get_data()
    if not data.get("custom_images"):
        await callback.message.answer("Загрузите хотя бы одно фото")
        return
    await state.set_state(CustomFSM.confirming)
    await _show_custom_confirm(callback.message, state, is_photo=bool(callback.message.photo))


# ── Комментарий ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "custom:add_comment")
async def cb_add_comment(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    await state.set_state(CustomFSM.writing_comment)
    await callback.message.answer(
        "💬 Напишите пожелания (расположение, цвет нитей, детали).\n"
        "Или отправьте «—» чтобы пропустить."
    )


@router.message(CustomFSM.writing_comment)
async def handle_comment(message: Message, state: FSMContext):
    comment = None if message.text.strip() == "—" else message.text.strip()
    await state.update_data(comment=comment)
    await state.set_state(CustomFSM.confirming)
    await message.answer("✅ Комментарий сохранён.")
    await _show_custom_confirm(message, state)


# ── Подтверждение ─────────────────────────────────────────────────────────────

async def _show_custom_confirm(msg: Message, state: FSMContext, is_photo: bool = False):
    data         = await state.get_data()
    type_name    = data.get("type_name", "—")
    color_name   = data.get("color_name", "—")
    size_label   = data.get("size_label", "—")
    print_name   = data.get("print_name")
    print_size_l = data.get("print_size_label")
    custom_imgs  = data.get("custom_images", [])
    comment      = data.get("comment")

    emb_line = (
        f"Принт: <b>{print_name}</b>, размер: <b>{print_size_l}</b>"
        if print_name
        else f"Ваши фото: {len(custom_imgs)} шт."
    )
    text = (
        f"📋 <b>Проверьте заявку</b>\n\n"
        f"Изделие: <b>{type_name}</b>\n"
        f"Цвет: <b>{color_name}</b>\n"
        f"Размер: <b>{size_label}</b>\n"
        f"Вышивка: {emb_line}\n"
        + (f"Комментарий: {comment}\n" if comment else "")
        + "\n⏳ Цена будет рассчитана после подтверждения администратором."
    )
    kb = custom_confirm_kb(has_comment=bool(comment))

    if is_photo:
        try:
            await msg.edit_caption(caption=text, reply_markup=kb)
            return
        except Exception:
            pass
    try:
        await msg.edit_text(text, reply_markup=kb)
    except Exception:
        await msg.answer(text, reply_markup=kb)


@router.callback_query(F.data == "custom:confirm", CustomFSM.confirming)
async def cb_custom_confirm(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback)
    data = await state.get_data()
    await to_text(callback, "⏳ Отправляем заявку...", None)

    order = await api.create_custom_order(
        telegram_id=callback.from_user.id,
        product_type_id=data["type_id"],
        color_id=data["color_id"],
        size_label=data["size_label"],
        print_id=data.get("print_id"),
        print_size_id=data.get("print_size_id"),
        custom_images=data.get("custom_images") or None,
        comment=data.get("comment"),
    )
    await state.clear()

    if not order:
        await callback.message.edit_text("❌ Не удалось отправить заявку. Попробуйте позже.")
        return

    await callback.message.edit_text(
        f"✅ <b>Заявка №{order['id']} отправлена!</b>\n\n"
        f"Ориентировочная стоимость: <b>{order['recommended_price']} ₽</b>\n\n"
        f"Мы рассмотрим заявку и свяжемся с вами для уточнения деталей.\n"
        f"Когда заявка будет принята — придёт ссылка на оплату 💳"
    )