from fastapi.testclient import TestClient

from codebase_knowledge.api import create_app


def test_console_lists_scans_without_source():
    client = TestClient(create_app())
    page = client.get("/")
    assert page.status_code == 200
    assert 'data-shell="studio"' in page.text
    created = client.post("/api/scans", json={"files": [{"path": "src/Demo.java", "content": "class Demo {}"}]})
    assert created.status_code == 200
    listed = client.get("/api/scans")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == created.json()["id"]
    assert "class Demo" not in listed.text
