"""An item needs review when an agent touched it after a person last confirmed it."""

from app.models import AuditEvent
from app.schemas.items import ItemCreate, ItemPatch
from app.services.agent_review import acknowledge, pending_review_items, review_flags
from app.services.items import create_item, patch_item
from app.services.principal import WEB, Principal, set_principal

AGENT = Principal(via="mcp", token_name="Claude Code")
NEW = ItemCreate(title="Stability protocol review", group="General Issues", owner_org="gensci")


def _agent_creates(db, program, user, **fields):
    set_principal(db, AGENT)
    item = create_item(db, actor=user, program=program, data=NEW.model_copy(update=fields))
    set_principal(db, WEB)
    return item


def test_an_item_a_person_created_needs_no_review(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    assert review_flags(db, [item]) == {item.id: False}
    assert pending_review_items(db, program.id) == []


def test_an_agent_created_item_needs_review(db, program, admin, vocab):
    item = _agent_creates(db, program, admin)
    assert review_flags(db, [item]) == {item.id: True}
    assert [row.id for row in pending_review_items(db, program.id)] == [item.id]


def test_acknowledging_clears_it_and_is_audited(db, program, admin, member, vocab):
    item = _agent_creates(db, program, admin)
    assert acknowledge(db, actor=member, item=item) is True
    assert review_flags(db, [item]) == {item.id: False}
    assert item.agent_ack_by == member.id
    event = db.query(AuditEvent).filter(AuditEvent.action == "acknowledged").one()
    assert event.actor_id == member.id
    assert event.via == "web"


def test_acknowledging_with_nothing_pending_is_a_no_op(db, program, admin, vocab):
    item = create_item(db, actor=admin, program=program, data=NEW)
    assert acknowledge(db, actor=admin, item=item) is False
    assert db.query(AuditEvent).filter(AuditEvent.action == "acknowledged").count() == 0


def test_a_person_editing_the_item_acknowledges_it(db, program, admin, vocab):
    item = _agent_creates(db, program, admin)
    patch_item(db, actor=admin, item=item, patch=ItemPatch(priority="p1"))
    assert review_flags(db, [item]) == {item.id: False}


def test_an_agent_edit_after_acknowledgement_needs_review_again(db, program, admin, vocab):
    item = _agent_creates(db, program, admin)
    acknowledge(db, actor=admin, item=item)
    set_principal(db, AGENT)
    patch_item(db, actor=admin, item=item, patch=ItemPatch(priority="p1"))
    assert review_flags(db, [item]) == {item.id: True}


def test_an_agent_posting_an_update_does_not_flag_the_item(db, program, admin, vocab):
    from app.services.updates import create_update

    item = create_item(db, actor=admin, program=program, data=NEW)
    set_principal(db, AGENT)
    create_update(db, actor=admin, item=item, body="Progress from the agent")
    assert review_flags(db, [item]) == {item.id: False}


def test_a_deleted_item_is_not_listed_for_review(db, program, admin, vocab):
    from app.services.items import delete_item

    item = _agent_creates(db, program, admin)
    delete_item(db, actor=admin, item=item)
    assert pending_review_items(db, program.id) == []
