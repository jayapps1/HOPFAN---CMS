from fastapi import APIRouter

from src.api.v1 import auth, health, me, system, workspace, operations, content, donations

# Future private/admin routers must add real authentication and permission/scope
# dependencies before inclusion. A URL prefix is never an access control.
# Child routers use the shared API_PREFIX when their routes are declared. This
# also keeps their full route templates available for safe request logging.
router = APIRouter()
router.include_router(health.router)
router.include_router(system.router)
router.include_router(auth.router)
router.include_router(me.router)
router.include_router(workspace.router)
router.include_router(operations.router)
router.include_router(content.router)
router.include_router(donations.router)
