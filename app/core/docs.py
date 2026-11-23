"""自托管 /docs：不依赖外网 CDN。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings


def register_docs(app: FastAPI) -> None:
    """把 /docs 挂到 app 上。"""
    # ---- 静态资源：Swagger UI 的 JS/CSS 放在 app/static/swagger/ ----
    static_dir = Path(__file__).parent.parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/docs", include_in_schema=False)
    async def custom_docs() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{settings.app_name} - 接口文档",
            swagger_js_url="/static/swagger/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger/swagger-ui.css",
        )
