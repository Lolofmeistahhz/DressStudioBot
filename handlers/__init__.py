from handlers.start   import router as start_router
from handlers.profile import router as profile_router
from handlers.catalog import router as catalog_router
from handlers.custom  import router as custom_router
from handlers.orders  import router as orders_router

all_routers = [
    start_router,
    profile_router,
    catalog_router,
    custom_router,
    orders_router,
]