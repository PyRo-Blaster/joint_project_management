"""Any authenticated user can read the user directory; anonymous users cannot."""


def test_member_can_list_directory(member_client, admin, member):
    response = member_client.get("/api/users/directory")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    by_id = {u["id"]: u for u in body["data"]}
    assert by_id[admin.id]["name"] == "Ada Admin"
    assert by_id[member.id]["org"] == "yarrow"
    # Brief must not leak sensitive fields.
    assert "email" not in body["data"][0]
    assert "role" not in body["data"][0]


def test_directory_requires_authentication(client):
    response = client.get("/api/users/directory")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
