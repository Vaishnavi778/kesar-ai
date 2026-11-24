from app.db import init_db, upsert_orders, upsert_customer, create_or_update_ticket, get_ticket, update_ticket_status


def test_ticket_persists_and_updates(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    init_db()
    cid = upsert_customer("Test User", "test@example.com")
    upsert_orders([{"order_id":"KC-9999","customer_email":"test@example.com","status":"shipped"}])
    data={"ticket_id":"TKT-TEST","customer_id":cid,"customer_name":"Test User","customer_email":"test@example.com",
          "email_subject":"Status","original_message":"Where is it?","intent":"order_status","sentiment":"neutral",
          "urgency":"medium","ai_response":"Your order is shipped.","status":"Awaiting Human Review",
          "escalation_reason":"Low AI confidence","confidence":0.4,"tool_results":{}}
    assert create_or_update_ticket(data) == "TKT-TEST"
    assert get_ticket("TKT-TEST")["status"] == "Awaiting Human Review"
    update_ticket_status("TKT-TEST","Approved","Approved reply")
    assert get_ticket("TKT-TEST")["status"] == "Approved"
