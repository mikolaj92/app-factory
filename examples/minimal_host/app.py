"""Smallest useful app-factory product host."""

from pathlib import Path

from app_factory import ProductAppConfig, create_product_app, template_response
from app_factory.platform import MenuItem, PlatformConfig
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return template_response(
        request.app.state.app_factory_product.environment, request, "home.html"
    )


app = create_product_app(
    ProductAppConfig(
        template_directory=Path(__file__).parent / "templates",
        platform=PlatformConfig(
            app_name="Small AI tool",
            menu=(MenuItem("Home", "/", key="home"),),
            show_register=False,
        ),
    ),
    routers=(router,),
)
