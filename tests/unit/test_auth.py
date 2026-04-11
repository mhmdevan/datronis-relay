from __future__ import annotations

import pytest

from datronis_relay.core.auth import AuthGuard
from datronis_relay.domain.errors import AuthError
from tests.conftest import make_message, make_user


class TestAuthGuard:
    def test_allowed_user_is_returned(self) -> None:
        user = make_user(user_id="telegram:42")
        guard = AuthGuard(users=[user])
        resolved = guard.authenticate(make_message("hello", user_id="telegram:42"))
        assert resolved is user

    def test_disallowed_user_raises(self) -> None:
        guard = AuthGuard(users=[make_user(user_id="telegram:42")])
        with pytest.raises(AuthError) as exc_info:
            guard.authenticate(make_message("hello", user_id="telegram:99"))
        assert exc_info.value.correlation_id is not None
        assert "not permitted" in str(exc_info.value)

    def test_empty_allowlist_is_rejected_at_construction(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            AuthGuard(users=[])

    def test_multiple_users_are_resolved_independently(self) -> None:
        alice = make_user(user_id="telegram:1", display_name="Alice")
        bob = make_user(user_id="telegram:2", display_name="Bob")
        guard = AuthGuard(users=[alice, bob])

        assert guard.authenticate(make_message("hi", user_id="telegram:1")) is alice
        assert guard.authenticate(make_message("hi", user_id="telegram:2")) is bob

    def test_user_permissions_are_preserved(self) -> None:
        user = make_user(
            user_id="telegram:42",
            allowed_tools=["Read", "Bash"],
            per_minute=5,
            per_day=50,
        )
        guard = AuthGuard(users=[user])
        resolved = guard.authenticate(make_message("hi", user_id="telegram:42"))
        assert resolved.allowed_tools == frozenset({"Read", "Bash"})
        assert resolved.rate_limit_per_minute == 5
        assert resolved.rate_limit_per_day == 50

    def test_auth_error_carries_category_and_correlation(self) -> None:
        guard = AuthGuard(users=[make_user(user_id="telegram:42")])
        message = make_message("hi", user_id="telegram:99")
        try:
            guard.authenticate(message)
        except AuthError as exc:
            text = exc.user_message()
            assert text.startswith("[AUTH]")
            assert message.correlation_id in text

    def test_cross_platform_ids_do_not_collide(self) -> None:
        """telegram:42 and slack:42 must be treated as different users."""
        telegram_user = make_user(user_id="telegram:42")
        slack_user = make_user(user_id="slack:42")
        guard = AuthGuard(users=[telegram_user, slack_user])
        assert guard.authenticate(make_message("hi", user_id="telegram:42")) is telegram_user
        assert guard.authenticate(make_message("hi", user_id="slack:42")) is slack_user
