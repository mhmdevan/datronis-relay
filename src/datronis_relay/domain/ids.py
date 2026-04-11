from __future__ import annotations

import uuid
from typing import NewType

UserId = NewType("UserId", str)
SessionId = NewType("SessionId", str)
CorrelationId = NewType("CorrelationId", str)


def new_session_id() -> SessionId:
    return SessionId(uuid.uuid4().hex)


def new_correlation_id() -> CorrelationId:
    return CorrelationId(uuid.uuid4().hex[:12])
