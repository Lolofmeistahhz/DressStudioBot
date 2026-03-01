"""services/api.py"""
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)
BASE = settings.API_BASE_URL.rstrip("/")
API_BASE_URL = settings.API_BASE_URL

def full_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http"):
        return path
    origin = BASE
    for suffix in ["/api/v1", "/api"]:
        if origin.endswith(suffix):
            origin = origin[: -len(suffix)]
            break
    return f"{origin}{path}"


def _patch_type(t: dict) -> dict:
    t["image_url"]         = full_url(t.get("image_url"))
    t["size_chart_url"]    = full_url(t.get("size_chart_url"))
    t["color_palette_url"] = full_url(t.get("color_palette_url"))
    return t


async def _get(url: str, **params) -> dict | list | None:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, params={k: v for k, v in params.items() if v is not None})
            if not r.is_success:
                logger.error(f"GET {url} → {r.status_code}: {r.text}")
                return None
            return r.json()
    except Exception as e:
        logger.error(f"GET {url}: {e}")
        return None


async def _post(url: str, body: dict) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, json=body)
            if not r.is_success:
                logger.error(f"POST {url} → {r.status_code}: {r.text}")
                return None
            return r.json()
    except Exception as e:
        logger.error(f"POST {url}: {e}")
        return None


async def _patch(url: str, body: dict, **params) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.patch(url, json=body, params={k: v for k, v in params.items() if v is not None})
            if not r.is_success:
                logger.error(f"PATCH {url} → {r.status_code}: {r.text}")
                return None
            return r.json()
    except Exception as e:
        logger.error(f"PATCH {url}: {e}")
        return None


async def _delete(url: str, **params) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.delete(url, params={k: v for k, v in params.items() if v is not None})
            if not r.is_success:
                logger.error(f"DELETE {url} → {r.status_code}: {r.text}")
                return None
            return r.json()
    except Exception as e:
        logger.error(f"DELETE {url}: {e}")
        return None


# ── Пользователи ──────────────────────────────────────────────────────────────

async def upsert_user(telegram_id: int, username: str | None, full_name: str | None) -> dict | None:
    return await _post(f"{BASE}/users/me", {
        "telegram_id": telegram_id, "username": username, "full_name": full_name,
    })

async def get_user(telegram_id: int) -> dict | None:
    return await _get(f"{BASE}/users/me", telegram_id=telegram_id)

async def set_phone(telegram_id: int, phone: str) -> dict | None:
    return await _patch(f"{BASE}/users/me/phone", {"phone": phone}, telegram_id=telegram_id)

async def update_delivery(telegram_id: int, **fields) -> dict | None:
    return await _patch(f"{BASE}/users/me/delivery", fields, telegram_id=telegram_id)


# ── Каталог ───────────────────────────────────────────────────────────────────

async def get_product_types() -> list | None:
    data = await _get(f"{BASE}/catalog/types")
    if data:
        for t in data:
            _patch_type(t)
    return data

async def get_product_type(type_id: int) -> dict | None:
    data = await _get(f"{BASE}/catalog/types/{type_id}")
    if data:
        _patch_type(data)
    return data

async def get_type_colors(type_id: int) -> list | None:
    return await _get(f"{BASE}/catalog/types/{type_id}/colors")

async def get_type_sizes(type_id: int) -> list | None:
    return await _get(f"{BASE}/catalog/types/{type_id}/sizes")

async def get_ready_products(product_type_id: int | None = None, color_id: int | None = None) -> list | None:
    data = await _get(f"{BASE}/catalog/ready", product_type_id=product_type_id, color_id=color_id)
    if data:
        for p in data:
            p["image_url"] = full_url(p.get("image_url"))
    return data

async def get_prints() -> list | None:
    data = await _get(f"{BASE}/catalog/prints")
    if data:
        for p in data:
            p["image_url"] = full_url(p.get("image_url"))
    return data


# ── Корзина ───────────────────────────────────────────────────────────────────

async def get_cart(telegram_id: int) -> dict | None:
    return await _get(f"{BASE}/cart/", telegram_id=telegram_id)

async def add_to_cart(telegram_id: int, ready_product_id: int, quantity: int = 1) -> dict | None:
    return await _post(f"{BASE}/cart/?telegram_id={telegram_id}", {
        "ready_product_id": ready_product_id, "quantity": quantity,
    })

async def update_cart_item(telegram_id: int, item_id: int, quantity: int) -> dict | None:
    return await _patch(f"{BASE}/cart/{item_id}", {"quantity": quantity}, telegram_id=telegram_id)

async def remove_cart_item(telegram_id: int, item_id: int) -> dict | None:
    return await _delete(f"{BASE}/cart/{item_id}", telegram_id=telegram_id)

async def clear_cart(telegram_id: int) -> dict | None:
    return await _delete(f"{BASE}/cart/", telegram_id=telegram_id)


# ── Заказы ────────────────────────────────────────────────────────────────────

async def create_ready_order(telegram_id: int) -> dict | None:
    return await _post(f"{BASE}/ready-orders/?telegram_id={telegram_id}", {})

async def get_my_ready_orders(telegram_id: int) -> list | None:
    return await _get(f"{BASE}/ready-orders/my", telegram_id=telegram_id)

async def create_custom_order(
    telegram_id: int, product_type_id: int, color_id: int, size_label: str,
    print_id: int | None = None, print_size_id: int | None = None,
    custom_images: list[str] | None = None, comment: str | None = None,
) -> dict | None:
    return await _post(f"{BASE}/custom-orders/?telegram_id={telegram_id}", {
        "product_type_id": product_type_id, "color_id": color_id,
        "size_label": size_label, "print_id": print_id,
        "print_size_id": print_size_id, "custom_images": custom_images, "comment": comment,
    })

async def get_my_custom_orders(telegram_id: int) -> list | None:
    return await _get(f"{BASE}/custom-orders/my", telegram_id=telegram_id)


# ── Оплата ────────────────────────────────────────────────────────────────────

async def create_payment(entity_type: str, entity_id: int, amount: float) -> dict | None:
    return await _post(f"{BASE}/payments/create", {
        "entity_type": entity_type, "entity_id": entity_id, "amount": str(amount),
    })


# ── Медиа ─────────────────────────────────────────────────────────────────────

async def upload_photo(file_data: bytes, filename: str) -> str | None:
    """
    Загружает фото на сервер.
    file_data: байты файла
    filename: имя файла
    """
    try:
        url = f"{API_BASE_URL}/upload"  # Убедитесь, что путь правильный
        files = {
            'file': (filename, file_data, 'image/jpeg')
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, files=files)

            if response.status_code != 200:
                logger.error(f"UPLOAD {response.status_code}: {response.text}")
                return None

            data = response.json()
            if data.get("success") and data.get("url"):
                # URL должен быть полным или относительным?
                # Если относительный - добавляем базовый URL
                img_url = data["url"]
                if img_url.startswith("/"):
                    img_url = f"{API_BASE_URL}{img_url}"
                return img_url
            else:
                logger.error(f"UPLOAD invalid response: {data}")
                return None

    except Exception as e:
        logger.error(f"UPLOAD error: {e}")
        return None