from __future__ import annotations

from collections.abc import Iterable

from datronis_relay.domain.errors import AuthError
from datronis_relay.domain.messages import PlatformMessage
from datronis_relay.domain.user import User


class AuthGuard:
    """Multi-user allowlist.

    Phase 1 had a frozenset of user ids; Phase 2 upgrades to a full `User`
    lookup that carries permissions and quotas. `authenticate()` either
    returns the resolved user or raises `AuthError`.
    """

    def __init__(self, users: Iterable[User]) -> None:
        self._by_id: dict[str, User] = {u.id: u for u in users}
        if not self._by_id:
            raise ValueError("AuthGuard requires at least one user")

    def authenticate(self, message: PlatformMessage) -> User:
        user = self._by_id.get(message.user_id)
        if user is None:
            raise AuthError(
                f"user {message.user_id} is not permitted",
                correlation_id=message.correlation_id,
            )
        return user
