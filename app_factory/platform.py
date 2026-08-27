"""Platform composition: shared chrome + optional passkey UI wiring.

Hosts call :func:`install_platform` for chrome-only installs, or
:func:`app_factory.adapters.install_identity_adapters` when wiring passkey and
usermanager UIs. Domain menu items are host-supplied. Fixed chrome:
main header = locale + theme; sidebar foot = signed-in account link or guest
Login (`platform_auth`); account page = Log out (`platform_session`). Hosts must
not reimplement these or put logout in chrome.

:class:`PlatformPaths` is the identity-lifecycle route contract (login, logout,
register, activation, recovery, account, credentials, users, invite). Opt-in
sidebar slots and ``PlatformUser.is_admin`` control link visibility; adapters
in my-auth / my-usermanager own the handlers. Shared Jinja shells
(``IDENTITY_PUBLIC_SHELL``, ``IDENTITY_AUTHENTICATED_SHELL``) compose those
surfaces into product chrome. Set ``PlatformPaths.root`` for a reverse-proxy
mount prefix.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from jinja2 import Environment

from app_factory.fastapi import AppFactoryUi, install_app_factory_ui

try:
    from fastapi import FastAPI
except ImportError as exc:  # pragma: no cover
    raise ImportError("app_factory.platform requires app-factory[fastapi]") from exc


@dataclass(frozen=True, slots=True)
class MenuItem:
    """One host navigation entry in the shared product sidebar.

    When ``use_htmx`` is true, the sidebar emits ``hx-get`` / ``hx-target`` /
    optional ``hx-select`` / ``hx-swap`` / ``hx-push-url``.
    ``no_htmx`` forces a plain link (auth and full-page routes).
    ``i18n`` sets ``data-i18n`` on the label span for client-side dictionaries.
    Empty ``hx_select`` omits the attribute (innerHTML partials that are not
    full-page fragments).
    """

    label: str
    href: str
    icon: str | None = None
    active: bool = False
    no_htmx: bool = False
    use_htmx: bool = False
    key: str | None = None
    badge: str | None = None
    i18n: str | None = None
    hx_target: str = "#main-content"
    hx_select: str | None = "#main-content"
    hx_swap: str = "outerHTML"


@dataclass(frozen=True, slots=True)
class MenuGroup:
    """Named group of navigation items (product / admin / etc.)."""

    label: str
    items: tuple[MenuItem, ...] = ()
    i18n: str | None = None


@dataclass(frozen=True, slots=True)
class PlatformLocale:
    """One language option for shared chrome.

    Prefer ``href`` for server-side locale switching (query/cookie). Omit
    ``href`` for client-side apps: chrome emits a button with
    ``data-platform-locale-select`` and ``data-locale`` so the host can
    handle ``platform:locale`` (see theme_boot) or bind its own listener.

    ``label`` is rendered as-is — prefer flag emoji (e.g. ``🇵🇱`` / ``🇬🇧``)
    for a compact language picker.
    """

    code: str
    label: str
    href: str | None = None


# Stable surface keys for the identity-lifecycle path contract.
IDENTITY_PUBLIC_SURFACES: tuple[str, ...] = (
    "login",
    "logout",
    "register",
    "activation",
    "recovery",
)
IDENTITY_AUTHENTICATED_SURFACES: tuple[str, ...] = (
    "account",
    "credentials",
)
IDENTITY_ADMIN_SURFACES: tuple[str, ...] = (
    "admin_users",
    "invite",
)
IDENTITY_SURFACES: tuple[str, ...] = (
    *IDENTITY_PUBLIC_SURFACES,
    *IDENTITY_AUTHENTICATED_SURFACES,
    *IDENTITY_ADMIN_SURFACES,
)

# Stable Jinja names for shared identity-lifecycle chrome composition.
IDENTITY_PUBLIC_SHELL = "app_factory/identity_public_shell.html"
IDENTITY_AUTHENTICATED_SHELL = "app_factory/identity_authenticated_shell.html"
IDENTITY_PUBLIC_STATE = "app_factory/identity_public_state.html"
IDENTITY_DENIED = "app_factory/identity_denied.html"
IDENTITY_DENIED_FRAGMENT = "app_factory/identity_denied_fragment.html"
# Slim TAP client document: Basecoat chrome without HTMX/Alpine.
CLIENT_SHELL = "app_factory/client_shell.html"


def join_platform_root(root: str, path: str) -> str:
    """Join a reverse-proxy / app mount root with an absolute path.

    ``root`` is empty or an absolute prefix such as ``/argus``. ``path`` must
    already be absolute (leading ``/``). Double-prefixing is refused when
    ``path`` already starts with ``root``.
    """
    normalized_root = (root or "").rstrip("/")
    if not path.startswith("/"):
        raise ValueError(f"platform path must be absolute, got {path!r}")
    if not normalized_root:
        return path
    if not normalized_root.startswith("/"):
        raise ValueError(f"platform root must be absolute, got {root!r}")
    if path == normalized_root or path.startswith(normalized_root + "/"):
        return path
    if path == "/":
        return normalized_root + "/"
    return f"{normalized_root}{path}"


@dataclass(frozen=True, slots=True)
class PlatformPaths:
    """Canonical identity-lifecycle URLs shared by adapter UIs and hosts.

    Defaults align with my-auth ``PasskeyPaths`` and my-usermanager HTMX paths.
    Adapters own the handlers; this type is the host-facing contract for links
    and navigation. Set ``root`` when the app is mounted behind a reverse-proxy
    prefix (e.g. ``/argus``); :meth:`resolved` prefixes every surface once.
    """

    login: str = "/login"
    logout: str = "/logout"
    register: str = "/register"
    recovery: str = "/recover"
    account: str = "/account"
    admin_users: str = "/admin/users"
    # Appended after the original positional fields for compatibility.
    activation: str = "/activate"
    credentials: str = "/account/passkeys"
    # GET form lives on the users list (UM v0.5.1+); POST stays /admin/users/invite.
    invite: str = "/admin/users"
    root: str = ""

    def href(self, surface: str) -> str:
        """Return the rooted URL for a named identity surface."""
        if surface not in IDENTITY_SURFACES:
            raise KeyError(f"unknown identity surface: {surface!r}")
        return join_platform_root(self.root, getattr(self, surface))

    def resolved(self) -> PlatformPaths:
        """Return paths with ``root`` baked into each surface (``root`` cleared)."""
        if not self.root:
            return self
        return PlatformPaths(
            login=self.href("login"),
            logout=self.href("logout"),
            register=self.href("register"),
            recovery=self.href("recovery"),
            account=self.href("account"),
            admin_users=self.href("admin_users"),
            activation=self.href("activation"),
            credentials=self.href("credentials"),
            invite=self.href("invite"),
            root="",
        )

    def public_hrefs(self) -> dict[str, str]:
        """Public lifecycle surfaces safe to expose without a session."""
        return {name: self.href(name) for name in IDENTITY_PUBLIC_SURFACES}

    def authenticated_hrefs(self) -> dict[str, str]:
        """Account surfaces that require an authenticated principal."""
        return {name: self.href(name) for name in IDENTITY_AUTHENTICATED_SURFACES}

    def admin_hrefs(self) -> dict[str, str]:
        """Admin surfaces; hosts still apply authorization before linking."""
        return {name: self.href(name) for name in IDENTITY_ADMIN_SURFACES}


@dataclass(frozen=True, slots=True)
class PlatformUser:
    """Minimal user view for shell templates (host maps session → this)."""

    display_name: str
    is_admin: bool = False
    user_id: str | None = None

    @property
    def avatar_initial(self) -> str:
        """First visible alphanumeric character for the fallback avatar."""
        return next(
            (character.upper() for character in self.display_name if character.isalnum()),
            "?",
        )

    @property
    def avatar_background(self) -> str:
        """Stable, dependency-free avatar color derived from the user identity."""
        palette = ("#9f1239", "#9a3412", "#3f6212", "#0f766e", "#1d4ed8", "#6d28d9")
        identity = self.user_id or self.display_name
        return palette[sum(identity.encode("utf-8")) % len(palette)]

    @property
    def avatar_foreground(self) -> str:
        """High-contrast foreground shared by the deliberately dark palette."""
        return "#ffffff"


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """Host-visible platform chrome configuration.

    ``menu`` accepts a flat list of :class:`MenuItem` and/or :class:`MenuGroup`.
    Flat items render as a single unlabeled list; groups render with headings
    (Basecoat ``role=group`` + ``h3``).
    """

    app_name: str = "App"
    brand_href: str = "/"
    brand_icon: str | None = None
    brand_meta: str | None = None
    brand_htmx: bool = False
    brand_hx_swap: str = "innerHTML"
    navigation_label: str | None = None
    menu: tuple[MenuItem | MenuGroup, ...] = ()
    paths: PlatformPaths = field(default_factory=PlatformPaths)
    # Identity navigation is opt-in so upgrades do not add unauthorized links.
    # Hosts map product authorization onto PlatformUser.is_admin (and these flags).
    enable_account: bool = False
    enable_credentials: bool = False
    enable_admin_users: bool = False
    enable_invite: bool = False
    identity_navigation_label: str = "Account"
    show_register: bool = True
    locales: tuple[PlatformLocale, ...] = ()
    default_locale: str | None = None
    # When true, menu items without no_htmx get use_htmx=True.
    htmx_nav: bool = False
    # Defaults applied when htmx_nav enables an item that still has stock values.
    default_hx_target: str = "#main-content"
    default_hx_select: str | None = "#main-content"
    default_hx_swap: str = "outerHTML"


@dataclass(frozen=True, slots=True)
class PlatformInstall:
    """Result of :func:`install_platform`."""

    ui: AppFactoryUi
    config: PlatformConfig
    passkey_ui: Any | None = None


def build_platform_context(
    config: PlatformConfig,
    *,
    user: PlatformUser | None = None,
    current_path: str = "",
    locales: Sequence[PlatformLocale] | None = None,
    locale: str | None = None,
) -> dict[str, Any]:
    """Build Jinja globals/context for product shell + platform foot.

    Pure function — safe for unit tests without FastAPI or WebAuthn.

    ``locales`` / ``locale`` override config defaults so hosts can inject
    per-request language links (e.g. preserve query on the current path).
    """
    paths = config.paths.resolved()
    menu = tuple(_resolve_menu_entry(entry, current_path, config) for entry in config.menu)
    identity_menu = _identity_navigation(config, user, current_path, paths)
    resolved_locales = tuple(locales) if locales is not None else config.locales
    resolved_locale = locale if locale is not None else config.default_locale
    return {
        "app_name": config.app_name,
        "platform_brand_href": config.brand_href,
        "platform_brand_icon": config.brand_icon,
        "platform_brand_meta": config.brand_meta,
        "platform_brand_htmx": config.brand_htmx or config.htmx_nav,
        "platform_brand_hx_swap": config.brand_hx_swap,
        "platform_navigation_label": config.navigation_label or config.app_name,
        "platform_menu": menu,
        "platform_identity_menu": identity_menu,
        "platform_identity_navigation_label": config.identity_navigation_label,
        "platform_user": user,
        "platform_paths": paths,
        "platform_path_root": config.paths.root,
        "platform_enable_account": config.enable_account,
        "platform_enable_credentials": config.enable_credentials,
        "platform_enable_admin_users": config.enable_admin_users,
        "platform_enable_invite": config.enable_invite,
        "platform_show_register": config.show_register,
        "platform_locales": resolved_locales,
        "platform_locale": resolved_locale,
        "platform_htmx_nav": config.htmx_nav,
        "login_url": paths.login,
    }


def _identity_navigation(
    config: PlatformConfig,
    user: PlatformUser | None,
    current_path: str,
    paths: PlatformPaths,
) -> tuple[MenuItem, ...]:
    """Build the enabled identity slot without taking over host authorization.

    Guests never receive authenticated/admin identity links. Admin surfaces
    additionally require ``PlatformUser.is_admin`` after the host has applied
    product policy when constructing that view.
    """
    if user is None:
        return ()

    candidates = (
        (
            config.enable_account,
            MenuItem("Account", paths.account, key="account", no_htmx=True),
        ),
        (
            config.enable_credentials,
            MenuItem(
                "Credentials",
                paths.credentials,
                key="credentials",
                no_htmx=True,
            ),
        ),
        (
            config.enable_admin_users and user.is_admin,
            MenuItem("Users", paths.admin_users, key="users", no_htmx=True),
        ),
        (
            config.enable_invite and user.is_admin,
            MenuItem("Invite", paths.invite, key="invite", no_htmx=True),
        ),
    )
    return tuple(
        _resolve_menu_item(item, current_path, config)
        for enabled, item in candidates
        if enabled
    )


def _resolve_menu_entry(
    entry: MenuItem | MenuGroup,
    current_path: str,
    config: PlatformConfig,
) -> MenuItem | MenuGroup:
    if isinstance(entry, MenuGroup):
        return MenuGroup(
            label=entry.label,
            i18n=entry.i18n,
            items=tuple(
                _resolve_menu_item(item, current_path, config) for item in entry.items
            ),
        )
    return _resolve_menu_item(entry, current_path, config)


def _resolve_menu_item(
    item: MenuItem,
    current_path: str,
    config: PlatformConfig,
) -> MenuItem:
    use_htmx = (item.use_htmx or config.htmx_nav) and not item.no_htmx
    # When HTMX is enabled via config defaults, fill stock hx_* from PlatformConfig.
    hx_target = item.hx_target
    hx_select = item.hx_select
    hx_swap = item.hx_swap
    if use_htmx and config.htmx_nav and not item.use_htmx:
        hx_target = config.default_hx_target
        hx_select = config.default_hx_select
        hx_swap = config.default_hx_swap
    return replace(
        item,
        active=item.active or _path_active(current_path, item.href),
        use_htmx=use_htmx,
        hx_target=hx_target,
        hx_select=hx_select,
        hx_swap=hx_swap,
    )


def _path_active(current_path: str, href: str) -> bool:
    if not current_path or not href:
        return False
    path_only = href.split("?", 1)[0]
    if current_path == path_only or current_path == href:
        return True
    return path_only != "/" and current_path.startswith(path_only.rstrip("/") + "/")


def apply_platform_context(
    environment: Environment,
    config: PlatformConfig,
    *,
    user: PlatformUser | None = None,
    current_path: str = "",
    locales: Sequence[PlatformLocale] | None = None,
    locale: str | None = None,
) -> Mapping[str, Any]:
    """Merge platform context into a Jinja environment's globals."""
    ctx = build_platform_context(
        config,
        user=user,
        current_path=current_path,
        locales=locales,
        locale=locale,
    )
    globals_dict = environment.globals
    globals_dict.update(ctx)
    return ctx


def install_platform(
    app: FastAPI,
    *,
    environments: Iterable[Environment],
    config: PlatformConfig | None = None,
    passkey_service: Any | None = None,
    passkey_hooks: Any | None = None,
    passkey_config: Any | None = None,
    usermanager_installer: Callable[[FastAPI, AppFactoryUi], Any] | None = None,
    static_path: str = "/static/platform",
    mount_name: str = "app-factory-platform",
) -> PlatformInstall:
    """Install shared chrome and optionally wire my-auth passkey UI.

    When ``passkey_service`` and ``passkey_hooks`` are provided, requires the
    ``platform`` (or at least ``my-auth[fastapi-htmx]``) extra and mounts the
    packaged passkey routes. Hosts still supply session hooks; they do not
    re-copy login templates or theme boot.
    """
    resolved = config or PlatformConfig()
    env_list = list(environments)
    ui = install_app_factory_ui(
        app,
        environments=env_list,
        static_path=static_path,
        mount_name=mount_name,
    )
    for environment in env_list:
        apply_platform_context(environment, resolved)

    passkey_ui = None
    if passkey_service is not None or passkey_hooks is not None:
        if passkey_service is None or passkey_hooks is None:
            raise ValueError(
                "passkey_service and passkey_hooks must both be provided to "
                "install passkey UI"
            )
        try:
            from app_factory.adapters.passkey import install_passkey_adapter
        except ImportError as exc:
            raise ImportError(
                "install_platform passkey wiring requires my-auth[fastapi-htmx] "
                "(install app-factory[platform])"
            ) from exc
        # my-auth ≥ v0.4.5 includes the router; do not include it again.
        passkey_ui = install_passkey_adapter(
            app,
            platform=ui,
            service=passkey_service,
            hooks=passkey_hooks,
            config=passkey_config,
            platform_config=resolved,
        )

    if usermanager_installer is not None:
        usermanager_installer(app, ui)

    app.state.app_factory_platform = PlatformInstall(
        ui=ui, config=resolved, passkey_ui=passkey_ui
    )
    return app.state.app_factory_platform


# Classes forbidden in platform-shipped templates (Basecoat 1.0 contract).
FORBIDDEN_BASECOAT_CLASS_MARKERS: tuple[str, ...] = (
    "btn-primary",
    "btn-secondary",
    "btn-destructive",
    "btn-ghost",
    "card-header",
    "card-content",
)
