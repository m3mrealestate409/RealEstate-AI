"""
Tenant deactivation and permanent deletion.

Two things are guarded here:

1. Deactivating a company must actually stop it. `Organization.is_active`
   existed and was editable, but was never checked anywhere — a "disabled"
   tenant's staff kept working normally. These tests pin the check itself and
   the fact that every entry point runs it.

2. A permanent delete must destroy the tenant's data but KEEP its payments.
   Payments are financial history; losing them with the customer is the kind of
   bug you only discover at audit time, so the invariant is asserted directly.
"""
import inspect

from app.api.v1 import auth as auth_api
from app.api.v1 import superadmin
from app.core import security
from app.services import orgpurge


# --------------------------------------------------------------------------
# Stubs — org_block_reason only touches these few attributes.
# --------------------------------------------------------------------------
class _Org:
    def __init__(self, is_active=True, deleted_at=None):
        self.is_active = is_active
        self.deleted_at = deleted_at


class _DB:
    def __init__(self, org):
        self._org = org

    def get(self, _model, _pk):
        return self._org


class _User:
    def __init__(self, is_super_admin=False, organization_id=1):
        self.is_super_admin = is_super_admin
        self.organization_id = organization_id


# --------------------------------------------------------------------------
# 1. The tenant gate
# --------------------------------------------------------------------------
def test_active_org_is_allowed():
    assert security.org_block_reason(_DB(_Org()), _User()) is None


def test_deactivated_org_is_blocked():
    reason = security.org_block_reason(_DB(_Org(is_active=False)), _User())
    assert reason and "deactivated" in reason.lower()


def test_deleted_org_is_blocked():
    reason = security.org_block_reason(_DB(_Org(deleted_at="2026-01-01")), _User())
    assert reason and "deleted" in reason.lower()


def test_missing_org_is_blocked():
    """A user whose organization row is gone must not fall through to allowed."""
    assert security.org_block_reason(_DB(None), _User()) is not None


def test_super_admin_is_never_blocked():
    """The platform owner has no organization — the gate must not lock them out
    of their own console while a tenant is suspended."""
    su = _User(is_super_admin=True, organization_id=None)
    assert security.org_block_reason(_DB(_Org(is_active=False)), su) is None


def test_gate_runs_on_every_entry_point():
    """Login alone is not enough: an already-issued JWT and an API key must stop
    working too, or a suspended tenant keeps running until its token expires."""
    assert "assert_org_allowed" in inspect.getsource(security.get_current_user)
    assert "assert_org_allowed" in inspect.getsource(auth_api.login)
    # Both branches of get_current_user (API key, then JWT) must be covered.
    assert inspect.getsource(security.get_current_user).count("assert_org_allowed") >= 2


def test_login_checks_tenant_only_after_password():
    """Checking the org before the password would leak which emails belong to a
    suspended company."""
    src = inspect.getsource(auth_api.login)
    assert src.index("verify_password") < src.index("assert_org_allowed")


# --------------------------------------------------------------------------
# 2. Permanent delete
# --------------------------------------------------------------------------
def test_purge_never_deletes_payments():
    src = inspect.getsource(orgpurge.purge)
    assert "wipe(Payment" not in src
    assert "delete(Payment" not in src


def test_purge_unlinks_payments_from_deleted_staff():
    """payments.recorded_by points at users. Keeping payments while deleting
    users only works if that link is nulled first — otherwise the users delete
    dies on a foreign-key error."""
    src = inspect.getsource(orgpurge.purge)
    assert "Payment.recorded_by" in src
    assert src.index("Payment.recorded_by") < src.index("wipe(User")


def test_purge_deletes_rag_chunks_before_projects():
    """Regression: rag_chunks reaches projects twice — via document (cascades)
    and via project_id directly (does NOT cascade). Only the document path was
    handled, so deleting a tenant with indexed documents failed on
    rag_chunks_project_id_fkey and rolled the whole purge back. Bulk SQL deletes
    do not run ORM cascades, so the chunks must go first, explicitly."""
    src = inspect.getsource(orgpurge.purge)
    assert "wipe(RagChunk" in src
    assert src.index("wipe(RagChunk") < src.index("wipe(Project")


def test_purge_deletes_children_before_users_and_projects():
    """Only some FKs cascade in Postgres; the rest must be removed in order."""
    src = inspect.getsource(orgpurge.purge)
    for child in ("wipe(QueryLog", "wipe(ChatSession", "wipe(Lead", "wipe(ApiKey"):
        assert child in src, f"{child} missing"
        assert src.index(child) < src.index("wipe(User")
    # Projects carry payment_plans.created_by -> users, so they go first too.
    assert src.index("wipe(Project") < src.index("wipe(User")


def test_purge_tombstones_the_org_instead_of_deleting_the_row():
    """The org row must survive: retained payments still reference it."""
    src = inspect.getsource(orgpurge.purge)
    assert "deleted_at" in src
    assert "wipe(Organization" not in src


def test_purge_frees_the_slug_and_clears_secrets():
    src = inspect.getsource(orgpurge.purge)
    assert "org.slug" in src                    # name can be reused later
    assert "crm_webhook_secret" in src          # stored credential is cleared


def test_delete_endpoint_requires_exact_name_match():
    src = inspect.getsource(superadmin.delete_org)
    assert "confirm_name" in src
    assert "org.name" in src


def test_delete_endpoint_rejects_already_deleted_org():
    src = inspect.getsource(superadmin.delete_org)
    assert "deleted_at is not None" in src


def test_deleted_orgs_are_hidden_from_the_platform_list():
    assert "deleted_at.is_(None)" in inspect.getsource(superadmin.list_orgs)
