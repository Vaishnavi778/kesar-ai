from app.engine import get_data, run_batch


EXPECTED = {
    "E01": ("order_status", False),
    "E02": ("product_query", False),
    "E03": ("return_refund", True),
    "E04": ("complaint", True),
    "E05": ("order_status", False),
    "E06": ("other", False),
    "E07": ("order_status", True),
    "E08": ("complaint", True),
    "E09": ("product_query", False),
    "E10": ("order_status", False),
    "E11": ("return_refund", True),
    "E12": ("return_refund", True),
    "E13": ("other", False),
    "E14": ("complaint", True),
    "E15": ("order_status", False),
    "E16": ("return_refund", True),
    "E17": ("other", False),
    "E18": ("order_status", True),
    "E19": ("return_refund", True),
    "E20": ("product_query", True),
    "E21": ("complaint", True),
    "E22": ("order_status", True),
    "E23": ("complaint", True),
    "E24": ("order_status", False),
    "E25": ("other", False),
}


def test_official_25_email_dataset_v2():
    orders, emails, faq, _ = get_data()
    audits, tickets = run_batch(emails, orders, faq)
    assert len(emails) == 25
    assert len(audits) == 25

    mismatch_intents = []
    mismatch_actions = []
    for audit in audits:
        expected_intent, expected_human = EXPECTED[audit["email_id"]]
        if audit["intent"] != expected_intent:
            mismatch_intents.append((audit["email_id"], expected_intent, audit["intent"]))
        if audit["needs_human"] != expected_human:
            mismatch_actions.append((audit["email_id"], expected_human, audit["needs_human"]))

    assert mismatch_intents == []
    assert mismatch_actions == []
    assert len(tickets) >= 9
