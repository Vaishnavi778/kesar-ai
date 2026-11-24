import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "kesar.db"


def connect():
    path = Path(__import__("os").environ.get("DATABASE_PATH", str(DB_PATH)))
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 5000")
    return con


def now():
    return datetime.now(timezone.utc).isoformat()


def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id INTEGER,
            product TEXT,
            order_date TEXT,
            status TEXT,
            tracking_id TEXT,
            tracking_url TEXT,
            estimated_delivery TEXT,
            payment_info TEXT,
            customer_email TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            customer_id INTEGER,
            customer_name TEXT,
            customer_email TEXT,
            email_subject TEXT,
            original_message TEXT,
            intent TEXT,
            sentiment TEXT,
            urgency TEXT,
            ai_response TEXT,
            status TEXT DEFAULT 'New',
            escalation_reason TEXT,
            confidence REAL,
            tool_results TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            email_id TEXT,
            action TEXT,
            details TEXT,
            created_at TEXT
        );
        """)


def upsert_customer(name, email):
    if not email:
        return None
    with connect() as con:
        con.execute("INSERT INTO customers(name,email) VALUES(?,?) ON CONFLICT(email) DO UPDATE SET name=excluded.name", (name or "", email.lower()))
        row = con.execute("SELECT id FROM customers WHERE email=?", (email.lower(),)).fetchone()
        return row["id"]


def upsert_orders(orders):
    with connect() as con:
        for order in orders:
            email = (order.get("customer_email") or "").lower()
            cid = None
            if email:
                con.execute(
                    "INSERT INTO customers(name,email) VALUES(?,?) ON CONFLICT(email) DO UPDATE SET name=excluded.name",
                    (order.get("customer_name") or "", email),
                )
                cid = con.execute("SELECT id FROM customers WHERE email=?", (email,)).fetchone()["id"]
            con.execute("""
            INSERT INTO orders(order_id,customer_id,product,order_date,status,tracking_id,tracking_url,estimated_delivery,payment_info,customer_email)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(order_id) DO UPDATE SET customer_id=excluded.customer_id,product=excluded.product,
            order_date=excluded.order_date,status=excluded.status,tracking_id=excluded.tracking_id,
            tracking_url=excluded.tracking_url,estimated_delivery=excluded.estimated_delivery,
            payment_info=excluded.payment_info,customer_email=excluded.customer_email
            """, (order.get("order_id"), cid, order.get("product"), order.get("order_date"),
                  order.get("status"), order.get("tracking_id"), order.get("tracking_url"),
                  order.get("estimated_delivery"), json.dumps(order.get("payment_info") or {}),
                  email))


def create_or_update_ticket(data):
    with connect() as con:
        existing = con.execute(
            "SELECT id,ticket_id FROM tickets WHERE ticket_id=?",
            (data.get("ticket_id"),)
        ).fetchone()
        if existing:
            con.execute("""
            UPDATE tickets SET customer_name=?,customer_email=?,email_subject=?,original_message=?,
            intent=?,sentiment=?,urgency=?,ai_response=?,status=?,escalation_reason=?,confidence=?,
            tool_results=?,updated_at=? WHERE id=?
            """, (data["customer_name"], data["customer_email"], data["email_subject"], data["original_message"],
                  data["intent"], data["sentiment"], data["urgency"], data["ai_response"], data["status"],
                  data["escalation_reason"], data["confidence"], json.dumps(data["tool_results"]), now(), existing["id"]))
            return existing["ticket_id"]
        con.execute("""
        INSERT INTO tickets(ticket_id,customer_id,customer_name,customer_email,email_subject,original_message,
        intent,sentiment,urgency,ai_response,status,escalation_reason,confidence,tool_results,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (data["ticket_id"], data.get("customer_id"), data["customer_name"], data["customer_email"],
              data["email_subject"], data["original_message"], data["intent"], data["sentiment"],
              data["urgency"], data["ai_response"], data["status"], data["escalation_reason"],
              data["confidence"], json.dumps(data["tool_results"]), now(), now()))
        return data["ticket_id"]


def add_audit(ticket_id, email_id, action, details):
    with connect() as con:
        existing = con.execute(
            "SELECT id FROM audit_logs WHERE email_id=? AND action=? AND coalesce(ticket_id,'')=? LIMIT 1",
            (email_id or "", action, ticket_id or ""),
        ).fetchone()
        if existing:
            return
        con.execute("INSERT INTO audit_logs(ticket_id,email_id,action,details,created_at) VALUES(?,?,?,?,?)",
                    (ticket_id or "", email_id or "", action, json.dumps(details, default=str), now()))


def list_tickets(status=None):
    with connect() as con:
        sql = "SELECT * FROM tickets"
        params = ()
        if status:
            sql += " WHERE status=?"
            params = (status,)
        sql += " ORDER BY created_at DESC"
        return [dict(r) for r in con.execute(sql, params)]


def get_ticket(ticket_id):
    with connect() as con:
        row = con.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,)).fetchone()
        return dict(row) if row else None


def update_ticket_status(ticket_id, status, ai_response=None, escalation_reason=None):
    with connect() as con:
        fields = ["status=?", "updated_at=?"]
        params = [status, now()]
        if ai_response is not None:
            fields.append("ai_response=?"); params.append(ai_response)
        if escalation_reason is not None:
            fields.append("escalation_reason=?"); params.append(escalation_reason)
        params.append(ticket_id)
        con.execute("UPDATE tickets SET " + ",".join(fields) + " WHERE ticket_id=?", params)


def list_audit_logs(limit=500):
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
