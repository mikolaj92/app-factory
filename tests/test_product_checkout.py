"""Product bootstrap must import from product.py even if helper modules vanish."""

from pathlib import Path

from app_factory import ProductAppConfig, create_product_app
from app_factory import product as product_module


def test_product_bootstrap_lives_in_product_module() -> None:
    package = Path(product_module.__file__).resolve().parent
    assert callable(product_module.route_paths)
    assert callable(product_module.product_http_error)
    assert create_product_app is product_module.create_product_app
    app = create_product_app(ProductAppConfig(template_directory=package / "templates"))
    assert app.state.app_factory_product.environment is not None
