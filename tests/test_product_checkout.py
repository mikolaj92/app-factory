"""Product helpers must be importable from the checked-out package (PR #85)."""

from pathlib import Path

from app_factory import ProductAppConfig, create_product_app
from app_factory import product as product_module
from app_factory import product_errors, product_routes


def test_product_bootstrap_imports_from_package_files() -> None:
    package = Path(product_module.__file__).resolve().parent
    assert (package / "product_routes.py").is_file()
    assert (package / "product_errors.py").is_file()
    assert callable(product_routes.route_paths)
    assert callable(product_errors.product_http_error)
    assert create_product_app is product_module.create_product_app
    app = create_product_app(ProductAppConfig(template_directory=package / "templates"))
    assert app.state.app_factory_product.environment is not None
