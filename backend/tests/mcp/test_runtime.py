"""Who is calling an MCP tool, and how a bad credential is refused."""

import pytest

from app.mcp.runtime import Caller, resolve_caller
from app.services.errors import UnauthenticatedError
from app.services.principal import current_principal
from app.services.tokens import create_token, revoke_token


def test_resolves_a_bearer_token_to_a_caller(db, admin):
    token, raw = create_token(db, actor=admin, owner=admin, name="Reader")
    caller = resolve_caller(db, {"authorization": f"Bearer {raw}"})
    assert isinstance(caller, Caller)
    assert caller.user.id == admin.id
    assert caller.token.id == token.id
    assert current_principal(db).via == "mcp"
    assert current_principal(db).token_name == "Reader"


def test_header_case_does_not_matter(db, admin):
    _, raw = create_token(db, actor=admin, owner=admin, name="Reader")
    assert resolve_caller(db, {"Authorization": f"bearer {raw}"}).user.id == admin.id


def test_a_missing_or_bad_token_is_refused(db, admin):
    for headers in ({}, {"authorization": "Bearer cmct_nope"}, {"authorization": "Basic x"}):
        with pytest.raises(UnauthenticatedError):
            resolve_caller(db, headers)


def test_a_cookie_is_not_accepted(db, admin):
    with pytest.raises(UnauthenticatedError):
        resolve_caller(db, {"cookie": "cmc_session=whatever"})


def test_a_revoked_token_is_refused(db, admin):
    token, raw = create_token(db, actor=admin, owner=admin, name="Doomed")
    revoke_token(db, actor=admin, token=token)
    with pytest.raises(UnauthenticatedError):
        resolve_caller(db, {"authorization": f"Bearer {raw}"})


def test_the_refusal_says_how_to_get_a_token(db, admin):
    with pytest.raises(UnauthenticatedError) as caught:
        resolve_caller(db, {})
    assert "Bearer cmct_" in caught.value.message
