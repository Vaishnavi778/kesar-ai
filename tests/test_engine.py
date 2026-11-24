from app.engine import classify, get_order, authorized, process_email

ORDERS=[{'order_id':'KC-1041','customer_email':'a@example.com','status':'shipped','estimated_delivery':'2026-11-21','tracking_url':'https://track.example.com/x'}]
FAQ='Saffron Glow Face Serum is suitable for all skin types including oily. It is vegan.'

def em(body, sender='a@example.com', subject='Question'):
    return {'id':'E1','from':{'name':'Ananya Rao','email':sender},'subject':subject,'body':body,'received_at':'2026-11-20T09:00:00+05:30'}

def test_extract_order_id_and_intent():
    x=classify(em('Where is my order KC-1041?'))
    assert x['intent']=='order_status' and x['order_id']=='KC-1041'

def test_email_lookup_and_privacy():
    assert get_order(ORDERS,None,'a@example.com')==ORDERS[0]
    assert authorized(ORDERS[0],'a@example.com')
    assert not authorized(ORDERS[0],'other@example.com')

def test_customer_data_not_disclosed_to_other_sender():
    a,_=process_email(em('Where is order KC-1041?','other@example.com'),ORDERS,FAQ,[])
    assert a['order_authorized'] is False
    assert 'track.example.com' not in a['draft_reply']
    assert a['needs_human'] is True

def test_complaint_creates_high_priority_ticket():
    ts=[]
    a,t=process_email(em('The item is damaged and leaking. KC-1041'),ORDERS,FAQ,ts)
    assert t['priority']=='High'
    assert a['needs_human'] is True

def test_product_query_grounded_from_faq():
    a,_=process_email(em('Is Saffron Glow serum vegan and suitable for oily skin?'),ORDERS,FAQ,[])
    assert 'suitable for all skin types' in a['draft_reply'].lower()

def test_low_confidence_and_refund_escalation_reason():
    ts=[]
    a,_=process_email(em('I want a refund for my damaged item','x@example.com'),ORDERS,FAQ,ts)
    assert a['needs_human'] is True
    assert 'damaged' in a['escalation_reason'].lower() or 'refund' in a['escalation_reason'].lower()
