"""Route inspection across eager and lazy FastAPI router inclusion."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from re import Pattern

from starlette.routing import BaseRoute, Mount, compile_path


@dataclass(frozen=True)
class RoutePath:
    path: str
    regex: Pattern[str]
    name: str | None
    methods: frozenset[str]
    mount: bool


def route_paths(routes: Iterable[BaseRoute], prefix: str = "") -> Iterator[RoutePath]:
    """Flatten lazy includes (new FastAPI) without changing routing behavior."""
    for route in routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            context = getattr(route, "include_context", None)
            nested_prefix = getattr(context, "prefix", None)
            if nested_prefix is None:
                continue
            yield from route_paths(included.routes, prefix + nested_prefix)
            continue
        path = prefix + getattr(route, "path", "")
        if not path:
            continue
        regex = getattr(route, "path_regex", None) if not prefix else None
        if regex is None:
            regex = compile_path(path)[0]
        yield RoutePath(
            path,
            regex,
            getattr(route, "name", None),
            frozenset(getattr(route, "methods", ()) or ()),
            isinstance(route, Mount),
        )


def check_reserved_routes(
    routes: Iterable[RoutePath], static: str, health: str, name: str
) -> None:
    for route in routes:
        if (
            route.name in (name, "app-factory-health")
            or route.path == health
            or route.path == static
            or route.path.startswith(static + "/")
            or route.regex.fullmatch(health)
            or route.regex.fullmatch(static + "/file.css")
            or (
                route.mount
                and (
                    health.startswith(route.path + "/")
                    or static.startswith(route.path + "/")
                )
            )
        ):
            raise ValueError(f"product host path/mount conflict: {route.path!r}")


def check_domain_routes(
    domain: Iterable[RoutePath], installed: Iterable[RoutePath]
) -> None:
    existing = list(installed)
    for route in domain:
        for other in existing:
            overlap = (
                route.path == other.path
                or other.regex.fullmatch(route.path)
                or route.regex.fullmatch(other.path)
                or (other.mount and route.path.startswith(other.path + "/"))
            )
            if overlap and (
                not route.methods or not other.methods or route.methods & other.methods
            ):
                raise ValueError(f"product host route conflict: {route.path!r}")
        existing.append(route)
