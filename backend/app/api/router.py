from fastapi import APIRouter

from app.api import activity, auth, health, invitations, items, users, vocab

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(users.router)
api_router.include_router(invitations.router)
api_router.include_router(vocab.router)
api_router.include_router(items.router)
