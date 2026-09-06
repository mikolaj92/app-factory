"""Product helpers must be present next to product.py in a clean checkout."""

from pathlib import Path

from app_factory import ProductAppConfig, create_product_app
from app_factory import product as product_module
from app_factory import product_errors, product_routes


def test_product_bootstrap_imports_focused_helper_modules() -> None:
    package = Path(product_module.__file__).resolve().parent
    assert (package / "product_routes.py").is_file()
    assert (package / "product_errors.py").is_file()
    assert product_module.route_paths is product_routes.route_paths
    assert product_module.product_http_error is product_errors.product_http_error
    assert create_product_app is product_module.create_product_app
    app = create_product_app(ProductAppConfig(template_directory=package / "templates"))
    assert app.state.app_factory_product.environment is not None
