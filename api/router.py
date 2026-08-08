from fastapi import APIRouter

from api.routes import auth, chat, conversations, database_connections, files, health, knowledge_bases, permissions

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(database_connections.router)
api_router.include_router(permissions.router)
api_router.include_router(files.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
