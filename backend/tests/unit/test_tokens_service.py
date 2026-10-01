"""The API token service: creation, listing, revocation, and resolution."""

from datetime import timedelta

import pytest

from app.models import AuditEvent
from app.models.base import utcnow
from app.services.errors import ConflictError, ForbiddenError, InvalidInputError
from app.services.tokens import (
    create_token,
    get_token,
    list_tokens,
    resolve_token,
    revoke_token,
)


def test_create_returns_the_raw_token_once_and_stores_only_a_hash(db, admin):
    record, raw = create_token(db, actor=admin, owner=admin, name="Claude Code")
    assert raw.startswith("cmct_")
    assert len(raw) > 40
    assert record.token_hash != raw
    assert raw not in record.token_hash
    assert record.prefix == raw[:12]
    assert record.scopes == "read"
    assert record.write_mode == "interactive"


def test_create_defaults_the_expiry_and_accepts_an_override(db, admin):
    record, _ = create_token(db, actor=admin, owner=admin, name="Default", ttl_days=90)
    assert record.expires_at is not None
    assert record.expires_at > utcnow() + timedelta(days=89)

    never, _ = create_token(db, actor=admin, owner=admin, name="Forever", ttl_days=0)
    assert never.expires_at is None


def test_only_an_admin_may_mint_a_non_expiring_token(db, member):
    with pytest.raises(ForbiddenError):
        create_token(db, actor=member, owner=member, name="Forever", ttl_days=0)


def test_a_member_cannot_mint_a_token_for_someone_else(db, member, admin):
    with pytest.raises(ForbiddenError):
        create_token(db, actor=member, owner=admin, name="Not mine")


def test_an_admin_may_mint_a_token_for_someone_else(db, admin, member):
    record, _ = create_token(db, actor=admin, owner=member, name="For Mo")
    assert record.user_id == member.id
    assert record.created_by == admin.id


def test_write_scope_is_recorded(db, admin):
    record, _ = create_token(db, actor=admin, owner=admin, name="Writer", scopes=["read", "write"])
    assert record.scope_set == {"read", "write"}


def test_read_is_always_implied(db, admin):
    record, _ = create_token(db, actor=admin, owner=admin, name="Writer", scopes=["write"])
    assert record.scope_set == {"read", "write"}


def test_an_unknown_scope_is_rejected(db, admin):
    with pytest.raises(InvalidInputError):
        create_token(db, actor=admin, owner=admin, name="Bad", scopes=["read", "admin"])


def test_an_unknown_write_mode_is_rejected(db, admin):
    with pytest.raises(InvalidInputError):
        create_token(db, actor=admin, owner=admin, name="Bad", write_mode="wildcard")


def test_a_blank_name_is_rejected(db, admin):
    with pytest.raises(InvalidInputError):
        create_token(db, actor=admin, owner=admin, name="   ")


def test_a_duplicate_active_name_for_the_same_owner_is_rejected(db, admin):
    create_token(db, actor=admin, owner=admin, name="Claude Code")
    with pytest.raises(ConflictError):
        create_token(db, actor=admin, owner=admin, name="claude code")


def test_a_revoked_name_can_be_reused(db, admin):
    record, _ = create_token(db, actor=admin, owner=admin, name="Claude Code")
    revoke_token(db, actor=admin, token=record)
    again, _ = create_token(db, actor=admin, owner=admin, name="Claude Code")
    assert again.id != record.id


def test_resolve_returns_the_token_and_stamps_last_used(db, admin):
    record, raw = create_token(db, actor=admin, owner=admin, name="Claude Code")
    assert record.last_used_at is None
    resolved = resolve_token(db, raw)
    assert resolved is not None
    assert resolved.id == record.id
    assert resolved.last_used_at is not None


def test_resolve_refuses_an_unknown_expired_or_revoked_token(db, admin):
    assert resolve_token(db, "cmct_nonsense") is None
    assert resolve_token(db, "") is None
    assert resolve_token(db, "not-even-prefixed") is None

    expired, raw_expired = create_token(db, actor=admin, owner=admin, name="Old")
    expired.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert resolve_token(db, raw_expired) is None

    live, raw_live = create_token(db, actor=admin, owner=admin, name="Live")
    revoke_token(db, actor=admin, token=live)
    assert resolve_token(db, raw_live) is None


def test_resolve_refuses_a_deactivated_users_token(db, admin, member):
    _, raw = create_token(db, actor=admin, owner=member, name="Mo token")
    assert resolve_token(db, raw) is not None
    member.is_active = False
    db.commit()
    assert resolve_token(db, raw) is None


def test_list_scopes_to_an_owner(db, admin, member):
    create_token(db, actor=admin, owner=admin, name="Mine")
    create_token(db, actor=admin, owner=member, name="Theirs")
    assert len(list_tokens(db)) == 2
    assert [token.name for token in list_tokens(db, owner_id=member.id)] == ["Theirs"]


def test_creating_and_revoking_are_audited(db, admin, member):
    target, _ = create_token(db, actor=admin, owner=member, name="Theirs")
    revoke_token(db, actor=admin, token=target)
    assert get_token(db, target.id).revoked_at is not None

    events = db.query(AuditEvent).filter(AuditEvent.entity_type == "api_token").all()
    assert {event.action for event in events} == {"created", "revoked"}
    assert all(event.actor_id == admin.id for event in events)


def test_revoking_twice_is_idempotent(db, admin):
    record, _ = create_token(db, actor=admin, owner=admin, name="Doomed")
    first = revoke_token(db, actor=admin, token=record).revoked_at
    assert revoke_token(db, actor=admin, token=record).revoked_at == first


def test_a_member_cannot_revoke_someone_elses_token(db, admin, member):
    record, _ = create_token(db, actor=admin, owner=admin, name="Admin token")
    with pytest.raises(ForbiddenError):
        revoke_token(db, actor=member, token=record)


def test_a_member_can_revoke_their_own_token(db, admin, member):
    record, _ = create_token(db, actor=admin, owner=member, name="Mo token")
    assert revoke_token(db, actor=member, token=record).revoked_at is not None
