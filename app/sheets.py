import os


def sync_rows(tickets_sheet=None, audit_sheet=None, ticket_row=None, audit_row=None):
    if not os.environ.get("GOOGLE_SHEET_ID"):
        return {"ok": False, "reason": "Google Sheets is not configured"}
    credentials_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not credentials_path or not os.path.exists(credentials_path):
        return {"ok": False, "reason": "Service account credentials are not available"}
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])
        if ticket_row:
            ws = sheet.worksheet(tickets_sheet or "Support Tickets")
            ws.append_row(ticket_row)
        if audit_row:
            ws = sheet.worksheet(audit_sheet or "Audit Logs")
            ws.append_row(audit_row)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "reason": "Google Sheets sync failed"}
