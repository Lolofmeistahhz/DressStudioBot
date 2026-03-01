"""
handlers/profile.py — один телефон, нет delivery_phone.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from keyboards.profile import profile_kb, delivery_kb, carrier_kb, phone_request_kb
from keyboards.main import main_menu
from services import api

router = Router()


class ProfileFSM(StatesGroup):
    waiting_phone    = State()
    editing_name     = State()
    editing_city     = State()
    editing_address  = State()


# ── Утилиты ───────────────────────────────────────────────────────────────────

async def _render_profile(telegram_id: int) -> tuple[str, object]:
    user = await api.get_user(telegram_id)
    if not user:
        return "❌ Не удалось загрузить профиль.", None

    carrier_map = {"cdek": "СДЭК", "yandex": "Яндекс Доставка"}
    ok = user.get("delivery_complete", False)

    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"Имя: <b>{user.get('full_name') or '—'}</b>\n"
        f"Телефон: <b>{user.get('phone') or 'не указан'}</b>\n\n"
        f"<b>📦 Данные доставки</b>\n"
        f"Получатель: <b>{user.get('delivery_name') or '—'}</b>\n"
        f"Город: <b>{user.get('delivery_city') or '—'}</b>\n"
        f"Адрес / ПВЗ: <b>{user.get('delivery_address') or '—'}</b>\n"
        f"Перевозчик: <b>{carrier_map.get(user.get('delivery_carrier') or '', '—')}</b>\n\n"
        + ("✅ Всё заполнено, можно делать заказ!" if ok
           else "⚠️ Заполните данные доставки для оформления заказов")
    )
    return text, profile_kb(ok)


async def _render_delivery_menu() -> tuple[str, object]:
    return "📦 <b>Данные доставки</b>\n\nЧто изменить?", delivery_kb()


# ── Профиль ───────────────────────────────────────────────────────────────────

@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message, state: FSMContext):
    await state.clear()
    text, kb = await _render_profile(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "profile:back")
async def cb_profile_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await _render_profile(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ── Телефон (один на всё) ─────────────────────────────────────────────────────

@router.callback_query(F.data == "profile:phone")
async def cb_change_phone(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileFSM.waiting_phone)
    await callback.message.answer(
        "📱 Поделитесь номером кнопкой или введите вручную:",
        reply_markup=phone_request_kb(),
    )
    await callback.answer()


@router.message(ProfileFSM.waiting_phone, F.contact)
async def handle_phone_contact(message: Message, state: FSMContext):
    await api.set_phone(message.from_user.id, message.contact.phone_number)
    await state.clear()
    text, kb = await _render_profile(message.from_user.id)
    await message.answer(f"✅ Телефон обновлён!\n\n{text}", reply_markup=kb)


@router.message(ProfileFSM.waiting_phone, F.text)
async def handle_phone_text(message: Message, state: FSMContext):
    await api.set_phone(message.from_user.id, message.text.strip())
    await state.clear()
    text, kb = await _render_profile(message.from_user.id)
    await message.answer(f"✅ Телефон обновлён!\n\n{text}", reply_markup=kb)


# ── Меню доставки ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile:delivery")
async def cb_delivery_menu(callback: CallbackQuery):
    text, kb = await _render_delivery_menu()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ── Имя получателя ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "dlv:name")
async def cb_edit_name(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileFSM.editing_name)
    await callback.message.answer("✏️ Введите имя получателя (ФИО):")
    await callback.answer()


@router.message(ProfileFSM.editing_name)
async def handle_name(message: Message, state: FSMContext):
    await api.update_delivery(message.from_user.id, delivery_name=message.text.strip())
    await state.clear()
    text, kb = await _render_delivery_menu()
    await message.answer(f"✅ Имя обновлено!\n\n{text}", reply_markup=kb)


# ── Город ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "dlv:city")
async def cb_edit_city(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileFSM.editing_city)
    await callback.message.answer("🏙 Введите город:")
    await callback.answer()


@router.message(ProfileFSM.editing_city)
async def handle_city(message: Message, state: FSMContext):
    await api.update_delivery(message.from_user.id, delivery_city=message.text.strip())
    await state.clear()
    text, kb = await _render_delivery_menu()
    await message.answer(f"✅ Город обновлён!\n\n{text}", reply_markup=kb)


# ── Адрес ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "dlv:address")
async def cb_edit_address(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileFSM.editing_address)
    await callback.message.answer(
        "🏠 Введите адрес или номер ПВЗ:\n\n"
        "<i>Пример: ул. Ленина 5, кв. 12\n"
        "или: СДЭК пункт выдачи №12345</i>"
    )
    await callback.answer()


@router.message(ProfileFSM.editing_address)
async def handle_address(message: Message, state: FSMContext):
    await api.update_delivery(message.from_user.id, delivery_address=message.text.strip())
    await state.clear()
    text, kb = await _render_delivery_menu()
    await message.answer(f"✅ Адрес обновлён!\n\n{text}", reply_markup=kb)


# ── Перевозчик ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "dlv:carrier")
async def cb_edit_carrier(callback: CallbackQuery):
    await callback.message.edit_text(
        "🚚 Выберите службу доставки:",
        reply_markup=carrier_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("carrier:"))
async def cb_carrier_chosen(callback: CallbackQuery):
    carrier = callback.data.split(":")[1]
    await api.update_delivery(callback.from_user.id, delivery_carrier=carrier)
    label = {"cdek": "СДЭК", "yandex": "Яндекс Доставка"}.get(carrier, carrier)
    text, kb = await _render_delivery_menu()
    await callback.message.edit_text(f"✅ Перевозчик: <b>{label}</b>\n\n{text}", reply_markup=kb)
    await callback.answer()