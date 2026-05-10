from aiogram import Router

from dealgoblin.bot.handlers_keywords import router as keywords_router
from dealgoblin.bot.handlers_menu import router as menu_router
from dealgoblin.bot.handlers_search import router as search_router

router = Router()
router.include_router(menu_router)
router.include_router(keywords_router)
router.include_router(search_router)
