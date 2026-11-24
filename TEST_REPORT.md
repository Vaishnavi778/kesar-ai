# Test Report - Kesar & Co. Support Copilot

**Candidate name:** Vaishnavi
**Platform used:** Python / Flask
**LLM used:** Google Gemini, optional; deterministic fallback used for recorded offline run

## 1. How correctness was judged

The expected intent and action were derived from `data/orders.json`, `data/faq.md`, and the
assignment routing rules. Every return/refund or complaint is expected to create or update
a ticket; missing or mismatched order details and medical questions require human review;
ordinary "other" messages are logged and need no customer reply.

## 2. Results per email

v1 is the original deterministic baseline present at the start of this implementation.
Its 10-email subset is recorded as an engineering reconstruction from that baseline.
v2 is the implementation in the current repository.

| Email | Expected intent | Expected action | v1 intent | v1 action | v1 | v2 intent | v2 action | v2 | Notes |
|---|---|---|---|---|---|---|---|---|---|
| E01 | order_status | Draft for authorized customer | order_status | Draft | Pass | order_status | Draft, no ticket | Pass | Verified order lookup |
| E02 | product_query | FAQ-grounded draft | product_query | FAQ draft | Pass | product_query | FAQ draft | Pass | |
| E03 | return_refund | Ticket + human review | return_refund | Ticket + human | Pass | return_refund | Ticket + human | Pass | |
| E04 | complaint | High-priority ticket + human | complaint | Ticket + human | Pass | complaint | Ticket + human | Pass | |
| E05 | order_status | Hinglish draft | order_status | Draft | Pass | order_status | Draft | Pass | |
| E06 | other | Log only | other | Log | Pass | other | Log only | Pass | |
| E07 | order_status | Privacy mismatch + human | order_status | Privacy human | Pass | order_status | Privacy human | Pass | |
| E08 | complaint | High-priority ticket + human | complaint | Ticket + human | Pass | complaint | Ticket + human | Pass | |
| E09 | product_query | FAQ shipping/COD answer | other | Log | Fail | product_query | FAQ draft | Pass | v2 improved Hindi/COD routing |
| E10 | order_status | Sender lookup, authorized draft | order_status | Draft | Pass | order_status | Draft | Pass | |
| E11 | return_refund | Ticket + human review | — | — | — | return_refund | Ticket + human | Pass | |
| E12 | return_refund | Ticket + human; ignore prompt injection | — | — | — | return_refund | Ticket + human | Pass | Prompt injection treated as untrusted |
| E13 | other | Log only | — | — | — | other | Log only | Pass | |
| E14 | complaint | High-priority ticket + human | — | — | — | complaint | Ticket + human | Pass | |
| E15 | order_status | Draft for authorized COD customer | — | — | — | order_status | Draft | Pass | |
| E16 | return_refund | Ticket + human; unopened-rule refusal | — | — | — | return_refund | Ticket + human | Pass | |
| E17 | other | Log only | — | — | — | other | Log only | Pass | |
| E18 | order_status | Missing order details + human | — | — | — | order_status | Missing-order human | Pass | |
| E19 | return_refund | Ticket + human; COD refund policy | — | — | — | return_refund | Ticket + human | Pass | |
| E20 | product_query | Medical question + human | — | — | — | product_query | Medical human | Pass | |
| E21 | complaint | Update existing ticket E04 | — | — | — | complaint | Updated TKT-002 | Pass | |
| E22 | order_status | Unknown order + human | — | — | — | order_status | Missing-order human | Pass | |
| E23 | complaint | High-priority ticket + human | — | — | — | complaint | Ticket + human | Pass | |
| E24 | order_status | Cancelled/refund status | — | — | — | order_status | Authorized draft | Pass | |
| E25 | other | Log only | — | — | — | other | Log only | Pass | |

## 3. Summary

| Metric | v1 baseline | v2 final |
|---|---:|---:|
| Emails run | 10 | 25 |
| Intent accuracy | 9/10 | 25/25 |
| Correct action | 9/10 | 25/25 |
| Valid normalized JSON/internal classification | 10/10 | 25/25 |
| Needs human | 3/10 | 15/25 |
| Tickets created or updated | 4 in subset | 9 records, including E21 update of TKT-002 |
| Gemini API calls | 0 | 0; no credentials supplied |
| Average tokens/cost | N/A | N/A |

## 4. What changed from v1 to v2

- Added official dataset loading and a 25-email regression suite.
- Added business-rule escalation for missing orders, damaged/missing items, medical questions,
  refunds, angry customers and order-ownership failures.
- Added duplicate-ticket prevention for repeated cases such as E04/E21.
- Added SQLite persistence, audit entries and editable human-review actions.
- Added Gemini JSON normalization/retry/fallback and optional Google Sheets synchronization.

## 5. Failures and remaining risks

| Item | What remains | Why | Next step |
|---|---|---|---|
| Gemini live execution | Not verified | No API key was supplied | Configure `GEMINI_API_KEY` and run E01-E25 |
| Google Sheets | Not verified | No sheet ID or service account was supplied | Configure credentials and inspect both tabs |
| Live email sending | Not implemented | Draft-only is the safe assignment behavior | Human approval should precede a real email connector |
| LLM ticket cost | Not measured | No API credentials or usage data | Track provider usage in audit records |

## Automated evidence

The recorded v2 evidence comes from:

```powershell
pytest -q
python run.py
curl.exe http://127.0.0.1:5000/health
```

A live E01-shaped request was also processed through `POST /api/process`. It returned
`intent: order_status`, `order_authorized: true`, and a draft containing the real
`KC-1041` status and tracking details. It did not send any external email.
