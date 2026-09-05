"""Smallest useful app-factory product host."""

from pathlib import Path

from app_factory import template_response
from app_factory.adapters import install_platform_request_context
from app_factory.platform import MenuItem, PlatformConfig, install_platform
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).parent
templates = Jinja2Templates(directory=ROOT / "templates")
app = FastAPI(title="Small AI tool", docs_url=None)
config = PlatformConfig(
    app_name="Small AI tool",
    menu=(MenuItem("Home", "/", key="home"),),
    show_register=False,
)
install_platform(app, environments=[templates.env], config=config)
install_platform_request_context(app, config=config, environments=[templates.env])


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return template_response(templates.env, request, "home.html")
