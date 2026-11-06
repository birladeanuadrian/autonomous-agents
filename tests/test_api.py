from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text


def project(client, key="DEMO"):
    response = client.post("/api/v1/projects", json={"key": key, "name": " Demo "})
    assert response.status_code == 201
    return response.json()


def issue(client, project_id, **values):
    response = client.post(
        f"/api/v1/projects/{project_id}/issues", json={"title": " First issue ", **values}
    )
    assert response.status_code == 201
    return response.json()


def test_core_workflow(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/api/v1/projects").json() == []
    p = project(client)
    assert p["name"] == "Demo"
    assert p["description"] == ""
    assert UUID(p["id"])
    assert datetime.fromisoformat(p["created_at"]).utcoffset().total_seconds() == 0
    assert client.get(f"/api/v1/projects/{p['id']}").json() == p
    assert client.get("/api/v1/projects").json() == [p]
    assert client.get(f"/api/v1/projects/{p['id']}/issues").json() == []
    i = issue(client, p["id"], description=" preserve whitespace \n")
    assert i["title"] == "First issue"
    assert i["description"] == " preserve whitespace \n"
    assert i["status"] == "todo"
    assert i["created_at"] == i["updated_at"]
    url = f"/api/v1/issues/{i['id']}"
    assert client.get(url).json() == i
    assert client.patch(url, json={"title": " First issue "}).json() == i
    for status in ["in_progress", "done", "todo"]:
        response = client.patch(url, json={"status": status})
        assert response.status_code == 200
        updated = response.json()
        assert updated["status"] == status
        assert updated["description"] == i["description"]
        assert updated["created_at"] == i["created_at"]
        assert datetime.fromisoformat(updated["updated_at"]) > datetime.fromisoformat(
            i["updated_at"]
        )
        i = updated
    assert client.patch(url, json={"description": ""}).json()["description"] == ""


def test_filtering_and_project_isolation(client):
    first = project(client)
    second = project(client, "OTHER")
    todo = issue(client, first["id"])
    done = issue(client, first["id"], status="done")
    issue(client, second["id"], status="done")
    url = f"/api/v1/projects/{first['id']}/issues"
    assert client.get(url).json() == [todo, done]
    assert client.get(url, params={"status": "done"}).json() == [done]
    assert client.get(url, params={"status": "in_progress"}).json() == []
    assert client.get(url, params={"status": "invalid"}).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"key": "a", "name": "Name"},
        {"key": "demo", "name": "Name"},
        {"key": "AB\n", "name": "Name"},
        {"key": "A" * 11, "name": "Name"},
        {"key": "AB", "name": " \t\n"},
        {"key": "AB", "name": "a" * 101},
        {"key": "AB", "name": None},
        {"key": "AB", "name": "Name", "description": None},
        {"key": "AB", "name": "Name", "description": "a" * 5001},
        {"key": "AB", "name": "Name", "id": str(uuid4())},
        {},
    ],
)
def test_project_validation(client, payload):
    assert client.post("/api/v1/projects", json=payload).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": " "},
        {"title": "a" * 201},
        {"title": None},
        {"title": "OK", "description": None},
        {"title": "OK", "status": None},
        {"title": "OK", "status": "invalid"},
        {"title": "OK", "description": "a" * 10001},
        {"title": "OK", "project_id": str(uuid4())},
    ],
)
def test_issue_validation(client, payload):
    p = project(client)
    assert client.post(f"/api/v1/projects/{p['id']}/issues", json=payload).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": None},
        {"description": None},
        {"status": None},
        {"title": " "},
        {"title": "a" * 201},
        {"description": "a" * 10001},
        {"status": "invalid"},
        {"project_id": str(uuid4())},
        {"updated_at": "2026-01-01"},
    ],
)
def test_patch_validation(client, payload):
    i = issue(client, project(client)["id"])
    url = f"/api/v1/issues/{i['id']}"
    assert client.patch(url, json=payload).status_code == 422
    assert client.get(url).json() == i


def test_missing_resources_and_malformed_ids(client):
    missing = uuid4()
    for path in [f"/projects/{missing}", f"/projects/{missing}/issues", f"/issues/{missing}"]:
        assert client.get("/api/v1" + path).status_code == 404
    assert (
        client.post(f"/api/v1/projects/{missing}/issues", json={"title": "Test"}).status_code == 404
    )
    assert client.patch(f"/api/v1/issues/{missing}", json={"status": "done"}).status_code == 404
    assert client.get("/api/v1/projects/bad-id").status_code == 422
    assert client.get("/api/v1/issues/bad-id").status_code == 422


def test_duplicate_key_and_concurrency(client):
    def create(_):
        return client.post("/api/v1/projects", json={"key": "SAME", "name": "Same"}).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(create, range(2))) == [201, 409]
    assert create(None) == 409
    assert len(client.get("/api/v1/projects").json()) == 1
    # Names may be repeated.
    assert (
        client.post("/api/v1/projects", json={"key": "DIFFERENT", "name": "Same"}).status_code
        == 201
    )


def test_stable_ordering_for_tied_timestamps(client, engine):
    p1 = project(client, "FIRST")
    p2 = project(client, "SECOND")
    issues = [issue(client, p1["id"]) for _ in range(3)]
    with engine.begin() as connection:
        connection.execute(text("UPDATE projects SET created_at = '2026-01-01T00:00:00Z'"))
        connection.execute(text("UPDATE issues SET created_at = '2026-01-01T00:00:00Z'"))
    assert [p["id"] for p in client.get("/api/v1/projects").json()] == sorted([p1["id"], p2["id"]])
    assert [i["id"] for i in client.get(f"/api/v1/projects/{p1['id']}/issues").json()] == sorted(
        i["id"] for i in issues
    )
