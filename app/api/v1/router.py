"""v1 路由汇总：新增模块只改这里一处。"""

from fastapi import APIRouter

from app.api.v1 import auth, todos, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(todos.router)
