"""
Regression guard for the seat-cap race condition (Sprint 1, H3).

Threat: create_user did count() then INSERT with no lock — concurrent requests
all passed the cap check before any committed (proven live: 6 parallel creates
put 10 users on a 5-seat plan). The fix serializes the check+insert per org with
a transaction-scoped Postgres advisory lock.

A true concurrency test needs parallel DB transactions (exercised live during
the fix: 1x201 + 5x403, capped at 5). This test locks in that the serialization
point is not silently removed.
"""
import inspect

from app.api.v1 import users


def test_seat_cap_check_is_serialized_by_advisory_lock():
    src = inspect.getsource(users.create_user)
    # The advisory lock must be taken before the seat-cap check runs.
    assert "pg_advisory_xact_lock" in src
    assert src.index("pg_advisory_xact_lock") < src.index(".count()")
