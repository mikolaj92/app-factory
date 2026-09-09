"""Ordered route checks for composed identity UI (no ceremony or host policy)."""

from collections.abc import Iterable

from starlette.routing import BaseRoute

from app_factory.product_routes import RoutePath, route_paths


def check_identity_routes(
    routes: Iterable[BaseRoute], identity_routes: Iterable[BaseRoute]
) -> None:
    """Reject earlier HTTP routes that intercept an installed identity surface.

    Inspect application-local paths: ASGI root_path is deployment metadata, not
    a second route prefix. Later catch-alls and disjoint HTTP methods are valid.
    """
    owned = {id(route) for route in identity_routes}
    earlier: list[RoutePath] = []
    for container in routes:
        for route in route_paths([container]):
            if id(container) in owned:
                for other in earlier:
                    if (
                        route.methods
                        and other.methods
                        and not route.methods & other.methods
                    ):
                        continue
                    if (
                        other.path == route.path
                        or other.regex.fullmatch(route.path)
                        or (other.mount and route.path.startswith(other.path + "/"))
                    ):
                        raise ValueError(
                            f"identity route {route.path!r} shadowed by {other.path!r}"
                        )
            earlier.append(route)
