from fastapi import APIRouter

from app.api import (
    activity,
    auth,
    dashboard,
    exports,
    health,
    imports,
    invitations,
    items,
    updates,
    users,
    vocab,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(users.router)
api_router.include_router(invitations.router)
api_router.include_router(vocab.router)
api_router.include_router(items.router)
api_router.include_router(updates.router)
api_router.include_router(dashboard.router)
api_router.include_router(imports.router)
api_router.include_router(exports.router)
