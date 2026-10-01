from app.models import AuditEvent
from app.services.audit import record_event
from app.services.principal import CLI, WEB, Principal, current_principal, set_principal


def test_defaults_to_web_when_unset(db):
    assert current_principal(db) == WEB
    assert current_principal(db).via == "web"


def test_set_and_read_back(db):
    set_principal(db, Principal(via="mcp", token_name="Alice laptop"))
    principal = current_principal(db)
    assert principal.via == "mcp"
    assert principal.token_name == "Alice laptop"


def test_record_event_stamps_web_by_default(db, raw_user):
    event = record_event(
        db,
        actor=raw_user,
        entity_type="user",
        entity_id=raw_user.id,
        action="updated",
        summary="changed something",
    )
    db.commit()
    assert event.via == "web"
    assert event.token_name is None


def test_record_event_stamps_the_session_principal(db, raw_user):
    set_principal(db, Principal(via="mcp", token_name="Meeting notes bot"))
    event = record_event(
        db,
        actor=raw_user,
        entity_type="item",
        entity_id=1,
        action="updated",
        summary="changed status",
    )
    db.commit()
    stored = db.get(AuditEvent, event.id)
    assert stored.via == "mcp"
    assert stored.token_name == "Meeting notes bot"


def test_cli_principal_is_available(db, raw_user):
    set_principal(db, CLI)
    event = record_event(
        db,
        actor=raw_user,
        entity_type="import",
        entity_id=1,
        action="imported",
        summary="imported a sheet",
    )
    db.commit()
    assert event.via == "cli"
