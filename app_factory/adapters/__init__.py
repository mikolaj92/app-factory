"""Focused identity-adapter composition helpers.

These modules own **install / session / shell glue** only. Passkey ceremony
stays in my-auth; user lifecycle stays in my-usermanager. Hosts supply paths,
persistence bindings, page context, and product policy hooks.
"""

from app_factory.adapters.compose import (
    IdentityAdapterConflict,
    IdentityInstall,
    PasskeyBinding,
    UserManagerBinding,
    install_identity_adapters,
)
from app_factory.adapters.passkey import (
    complete_passkey_hooks,
    install_passkey_adapter,
    passkey_paths_from_platform,
)
from app_factory.adapters.session import (
    attach_platform_page_context,
    install_platform_request_context,
)
from app_factory.adapters.usermanager import (
    install_usermanager_adapter,
    usermanager_config_from_platform,
)

__all__ = [
    "IdentityAdapterConflict",
    "IdentityInstall",
    "PasskeyBinding",
    "UserManagerBinding",
    "attach_platform_page_context",
    "complete_passkey_hooks",
    "install_identity_adapters",
    "install_passkey_adapter",
    "install_platform_request_context",
    "install_usermanager_adapter",
    "passkey_paths_from_platform",
    "usermanager_config_from_platform",
]
