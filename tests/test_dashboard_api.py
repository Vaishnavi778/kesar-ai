from app.main import app


def test_dashboard_health_and_api_routes():
    client = app.test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/api/analytics").status_code == 200
    assert client.get("/api/search?q=KC-1047").status_code == 200
    assert client.get("/api/knowledge?q=damaged").status_code == 200
    assert client.get("/api/audit").status_code == 200


def test_ticket_lifecycle_api():
    client = app.test_client()
    response = client.post("/api/tickets/TKT-001/approve",
                           json={"response": "Human-approved test response"})
    assert response.status_code == 200
    assert response.get_json()["status"] == "Approved"
    response = client.post("/api/tickets/TKT-001/resolve")
    assert response.status_code == 200
    assert response.get_json()["status"] == "Resolved"
