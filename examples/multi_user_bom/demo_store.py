"""In-memory multi-user demo state for the BOM reference host.

Seeds two active users with distinct credentials and wires invitation /
recovery capabilities through my-auth + my-usermanager domain APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Final

from my_auth import (
    MemoryChallengeStore,
    MemoryCredentialStore,
    PasskeyConfig,
    PasskeyCredential,
    PasskeyService,
    PasskeyUser,
    VerifiedRegistration,
    registration_context_from_capability,
)
from my_auth.enrollment import MemoryEnrollmentCapabilityStore
from my_usermanager import (
    ExternalIdentity,
    MemoryAuditStore,
    MemoryGrantStore,
    MemoryRoleStore,
    MemoryUserStore,
    Permission,
    Scope,
    User,
    UserManager,
)
from my_usermanager.adapters.fastapi_htmx import (
    ExternalIdentityRow,
    InvitationRow,
    PermissionGrantRow,
    UserRow,
    row_key_from_user_id,
)
from my_usermanager.adapters.my_auth_enrollment import build_enrollment_capability_issuer
from my_usermanager.invitations import (
    Invitation,
    InvitationGrant,
    InvitationService,
    MemoryInvitationStore,
)
from my_usermanager.subjects import AuthenticatedSubject

ADMIN_ID: Final = "admin"
MEMBER_ID: Final = "member"
CSRF_HEADER: Final = "X-Demo-CSRF"
CSRF_TOKEN: Final = "demo-bom-csrf"
SESSION_COOKIE: Final = "bom_demo_user"
PROVIDER: Final = "my-auth"


@dataclass(frozen=True, slots=True)
class DemoUser:
    user_id: str
    username: str
    display_name: str
    email: str
    is_admin: bool = False


class DemoStore:
    """Mutable demo graph shared by passkey and usermanager hooks."""

    def __init__(self) -> None:
        self.users: dict[str, DemoUser] = {
            ADMIN_ID: DemoUser(
                ADMIN_ID,
                "admin",
                "Ada Admin",
                "admin@example.invalid",
                is_admin=True,
            ),
            MEMBER_ID: DemoUser(
                MEMBER_ID,
                "member",
                "Morgan Member",
                "member@example.invalid",
            ),
        }
        self.passkey_users = {
            user_id: PasskeyUser(
                user_id=user_id,
                user_handle=f"handle:{user_id}".encode(),
                name=user.username,
                display_name=user.display_name,
            )
            for user_id, user in self.users.items()
        }
        self.credentials = MemoryCredentialStore()
        self._seed_credentials()
        self.challenges = MemoryChallengeStore()
        self.passkey_service = PasskeyService(
            config=PasskeyConfig(
                rp_id="localhost",
                rp_name="Multi-user BOM demo",
                origin="http://localhost",
            ),
            challenges=self.challenges,
            credentials=self.credentials,
        )
        self.enrollment = MemoryEnrollmentCapabilityStore(
            now=lambda: datetime.now(UTC)
        )
        self.um_users = MemoryUserStore()
        self.roles = MemoryRoleStore()
        self.grants = MemoryGrantStore()
        self.audit = MemoryAuditStore()
        self.invitations = MemoryInvitationStore()
        self._seed_usermanager()
        self.invitation_service = InvitationService(
            manager=self.manager,
            users=self.um_users,
            identities=_IdentityBridge(self.um_users),
            invitations=self.invitations,
            enrollment=build_enrollment_capability_issuer(self.enrollment),
            audit=self.audit,
        )
        self.issued_invites: list[tuple[str, str]] = []
        self.issued_recoveries: list[tuple[str, str]] = []

    def _seed_credentials(self) -> None:
        admin = self.passkey_users[ADMIN_ID]
        member = self.passkey_users[MEMBER_ID]
        for user, credential_id, label in (
            (admin, b"admin-laptop", "Admin laptop"),
            (admin, b"admin-phone", "Admin phone"),
            (member, b"member-key", "Member passkey"),
        ):
            self.credentials.save_registration(
                VerifiedRegistration(
                    user,
                    PasskeyCredential(
                        credential_id,
                        user.user_id,
                        b"pubkey-" + credential_id,
                        label=label,
                    ),
                )
            )

    def _seed_usermanager(self) -> None:
        for user in self.users.values():
            self.um_users.create(
                User(
                    user_id=user.user_id,
                    username=user.username,
                    display_name=user.display_name,
                    email=user.email,
                    status="active",
                    external_identities=frozenset(
                        {ExternalIdentity(PROVIDER, user.user_id)}
                    ),
                )
            )
        self.manager = UserManager(self.um_users, self.roles, self.grants)
        self.grants.add_permission_grant(
            ADMIN_ID, Permission("users.invite"), Scope.global_()
        )
        self.grants.add_role_grant(ADMIN_ID, "admin", Scope.global_())
        self.grants.add_permission_grant(
            MEMBER_ID, Permission("users.read"), Scope.global_()
        )

    def subject(self, user_id: str) -> AuthenticatedSubject | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        return AuthenticatedSubject(
            provider=PROVIDER,
            subject=user.user_id,
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
        )

    def user_rows(self) -> tuple[UserRow, ...]:
        rows: list[UserRow] = []
        for user in self.users.values():
            um = self.um_users.get(user.user_id)
            rows.append(
                UserRow(
                    user_id=user.user_id,
                    row_key=row_key_from_user_id(user.user_id),
                    username=user.username,
                    display_name=user.display_name,
                    email=user.email,
                    disabled=bool(um and um.disabled),
                    is_admin=user.is_admin,
                    roles=tuple(
                        grant.role_name
                        for grant in self.grants.list_grants_for_user(user.user_id)
                        if grant.role_name
                    ),
                    permissions=tuple(
                        PermissionGrantRow(
                            permission=grant.permission.name,
                            label=grant.permission.name,
                            scope_type=grant.scope.scope_type,
                            scope_id=grant.scope.scope_id,
                        )
                        for grant in self.grants.list_grants_for_user(user.user_id)
                        if grant.permission is not None
                    ),
                    external_identities=(
                        ExternalIdentityRow(provider=PROVIDER, subject=user.user_id),
                    ),
                    account_status=um.status if um is not None else None,
                    invitation=self._invitation_row(user.user_id),
                )
            )
        return tuple(rows)

    def credentials_for(self, user_id: str) -> list[PasskeyCredential]:
        return list(self.credentials.list_credentials_for_user(user_id))

    def issue_invite(
        self,
        *,
        actor_id: str,
        username: str,
        email: str,
        role: str,
    ) -> tuple[str, str]:
        pending = User(
            user_id=username,
            username=username,
            display_name=username.title(),
            email=email,
            status="pending",
        )
        grant = (
            InvitationGrant(role_name="admin")
            if role == "admin"
            else InvitationGrant(permission=Permission("users.read"))
        )
        issued = self.invitation_service.invite(
            actor_id=actor_id,
            user=pending,
            grants=(grant,),
            ttl_seconds=3600,
        )
        self.users[username] = DemoUser(
            username,
            username,
            username.title(),
            email,
            is_admin=role == "admin",
        )
        self.passkey_users[username] = PasskeyUser(
            user_id=username,
            user_handle=f"handle:{username}".encode(),
            name=username,
            display_name=username.title(),
        )
        pair = (issued.invitation.invitation_id, issued.token)
        self.issued_invites.append(pair)
        return pair

    def reissue_invite(self, *, actor_id: str, invitation_id: str) -> tuple[str, str]:
        issued = self.invitation_service.reissue(
            actor_id=actor_id,
            invitation_id=invitation_id,
            ttl_seconds=3600,
        )
        pair = (issued.invitation.invitation_id, issued.token)
        self.issued_invites = [
            pair if item[0] == invitation_id else item for item in self.issued_invites
        ]
        if pair not in self.issued_invites:
            self.issued_invites.append(pair)
        return pair

    def revoke_invite(self, *, actor_id: str, invitation_id: str) -> Invitation:
        return self.invitation_service.revoke(
            actor_id=actor_id, invitation_id=invitation_id
        )

    def _invitation_row(self, user_id: str) -> InvitationRow | None:
        invitation = self.invitations.get_pending_for_user(user_id)
        if invitation is None:
            invitation = next(
                (
                    item
                    for item in self.invitations._invitations.values()  # noqa: SLF001
                    if item.user_id == user_id
                ),
                None,
            )
        if invitation is None:
            return None
        return InvitationRow(
            invitation_id=invitation.invitation_id,
            status=invitation.status,
            expires_at=invitation.expires_at.isoformat(),
        )

    def issue_recovery(self, *, subject: str, issued_by: str) -> str:
        issued = self.enrollment.issue(
            subject=subject,
            purpose="account_recovery",
            ttl_seconds=3600,
            issued_by=issued_by,
        )
        self.issued_recoveries.append((subject, issued.token))
        return issued.token

    def claim_capability(
        self,
        *,
        token: str,
        flow_id: str,
        kind: str,
    ):
        purpose = "invitation" if kind == "invitation" else "account_recovery"
        capability = self.enrollment.claim(
            token=token,
            flow_id=flow_id,
            expected_purpose=purpose,
        )
        user = self.passkey_users[capability.subject]
        return registration_context_from_capability(
            kind="invitation" if kind == "invitation" else "recovery",
            user=user,
            capability_id=capability.capability_id,
            capability_subject=capability.subject,
            capability_purpose=capability.purpose,
        )


class _IdentityBridge:
    """Minimal ExternalIdentityUserStore over MemoryUserStore."""

    def __init__(self, users: MemoryUserStore) -> None:
        self._users = users

    def create(self, user: User) -> User:
        return self._users.create(user)

    def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def get_by_username(self, username: str) -> User | None:
        return self._users.get_by_username(username)

    def update(self, user: User) -> User:
        return self._users.update(user)

    def list(self, **kwargs):
        return self._users.list(**kwargs)

    def count_active(self) -> int:
        return self._users.count_active()

    def resolve_external_identity(self, identity: ExternalIdentity) -> User | None:
        for user in self._users._users.values():  # noqa: SLF001 — demo bridge
            if identity in user.external_identities:
                return user
        return None

    def link_external_identity(
        self, *, user_id: str, identity: ExternalIdentity
    ) -> User:
        user = self.get(user_id)
        if user is None:
            raise ValueError("missing user")
        return self.update(
            replace(
                user,
                external_identities=user.external_identities | frozenset({identity}),
            )
        )
