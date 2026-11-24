"""Kesar & Co. support copilot core. Deterministic safeguards wrap optional LLM output."""
import json, re, os
from datetime import datetime, date
from pathlib import Path
from .gemini import classify_with_gemini

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
SCENARIO_TODAY = date(2026, 11, 20)
INTENTS = {'order_status','product_query','return_refund','complaint','other'}


def load_json(name, fallback):
    p = DATA / name
    if p.exists():
        try: return json.loads(p.read_text(encoding='utf-8'))
        except Exception: pass
    return fallback


def get_data():
    orders = load_json('orders.json', {'orders': []}).get('orders', [])
    emails = load_json('test_emails.json', {'emails': []}).get('emails', [])
    faq = (DATA / 'faq.md').read_text(encoding='utf-8') if (DATA/'faq.md').exists() else ''
    voice = (DATA / 'brand_voice.md').read_text(encoding='utf-8') if (DATA/'brand_voice.md').exists() else ''
    return orders, emails, faq, voice


def classify(email):
    body = (email.get('body') or '').lower(); subject=(email.get('subject') or '').lower()
    text = subject + ' ' + body
    oid = re.search(r'KC-\d{4}', text, re.I)
    if any(x in text for x in ['collab','gst invoice','gstin','seo rankers','free #1 google ranking','website selected']) or subject.strip() == 'thank you':
        intent='other'
    elif any(x in text for x in ['damaged','leak','cracked','broken','wrong item','missing item','is missing','missing from','worst experience','unacceptable','complaint']): intent='complaint'
    elif any(x in text for x in ['return','refund','money back','cancel']): intent='return_refund'
    elif not oid and any(x in text for x in ['cod','cash on delivery','डिलीवरी', 'कितने दिन']):
        intent='product_query'
    elif any(x in text for x in ['when will','where is','tracking','delivery','deliver','order status','order status','kab aayega','order no','डिलीवरी','order kab',' status of ']): intent='order_status'
    elif any(x in text for x in ['vegan','skin','serum','toner','oil','eczema','ingredients','oily','suitable','price','cod','cash on delivery','कौन से','उपलब्ध']): intent='product_query'
    else: intent='other'
    angry = any(x in text for x in ['worst','unacceptable','immediately','refund now','!!!','posting pictures','fraud'])
    sentiment = 'angry' if angry else ('negative' if intent in ('complaint','return_refund') else 'neutral')
    lang = 'hinglish' if re.search(r'\b(maine|kab|aayega|hai|pls|mujhe|mera|nahi)\b', body) else 'en'
    summary = re.sub(r'\s+',' ', email.get('subject') or body)[:195]
    fallback = {
        'customer_name': (email.get('from') or {}).get('name',''),
        'customer_email': (email.get('from') or {}).get('email',''),
        'order_id': oid.group(0).upper() if oid else None,
        'intent': intent,
        'product': '',
        'customer_issue': body[:500],
        'sentiment': sentiment,
        'urgency': 'high' if sentiment == 'angry' else 'medium',
        'required_action': 'get_order' if intent == 'order_status' else ('search_faq' if intent == 'product_query' else 'human_review'),
        'confidence': 0.88 if intent!='other' else 0.72,
        'summary': summary,
        'language': lang,
    }
    classified, source = classify_with_gemini(email, fallback)
    classified['secondary_intent'] = None
    classified['language'] = lang
    classified['classification_source'] = source
    return classified


def get_order(orders, order_id=None, sender=None):
    if order_id:
        for o in orders:
            if o.get('order_id','').lower()==order_id.lower(): return o
    if sender:
        matches=[o for o in orders if o.get('customer_email','').lower()==sender.lower()]
        return matches[0] if len(matches)==1 else None
    return None


def authorized(order, sender):
    return bool(order and sender and order.get('customer_email','').lower()==sender.lower())


def search_faq(faq, terms):
    if not faq: return ''
    lines=faq.splitlines(); hits=[]
    words=[w for w in re.findall(r'[a-z]{3,}', terms.lower()) if w not in {'the','and','for','with','about','from','your','you'}]
    for i,line in enumerate(lines):
        if any(w in line.lower() for w in words): hits.append(line)
    return '\n'.join(hits[:8])


def draft_reply(email, info, order, faq, authorized_order):
    name=(email.get('from') or {}).get('name','there').split()[0]
    intent=info['intent']; body=(email.get('body') or '').lower()
    if order and not authorized_order:
        return f"Hi {name},\n\nFor your privacy, we can only share order information with the email address used at checkout. Please write to us from the registered email address and we’ll be happy to help.\n\nWarm regards,\nTeam Kesar"
    if intent=='order_status':
        if not order: answer='We couldn’t safely locate your order from the details provided. Please reply with your order ID or contact us from the email used at checkout, and our team will check it.'
        else:
            status=order.get('status','status unavailable').replace('_',' ')
            answer=f"Your order {order['order_id']} is currently {status}."
            if order.get('estimated_delivery'): answer+=f" The estimated delivery date is {order['estimated_delivery']} (subject to courier updates)."
            if order.get('tracking_url'): answer+=f" You can track it here: {order['tracking_url']}"
    elif intent=='product_query':
        hits=search_faq(faq, email.get('subject','')+' '+email.get('body',''))
        if not hits: answer='We don’t have a verified answer to this question in our product guide, so I’m asking a team member to review it and follow up within 24 business hours.'
        else: answer='Based on our product guide: '+ ' '.join(x.strip('- ') for x in hits.splitlines()[:3] if x.strip())
        if any(x in body for x in ['eczema','pregnan','allerg','psoriasis','severe acne','cure','treat']): answer='For medical, pregnancy or allergy-related questions, please consult a dermatologist or doctor. Our products are cosmetics, not medicines, and we cannot provide medical advice.'
    elif intent in ('return_refund','complaint'):
        if not order: answer='I’m sorry for the trouble. We couldn’t safely match an order to your message, so our support team needs to review this. A team member will follow up within 24 business hours.'
        else: answer=f"I’m sorry for the inconvenience with order {order['order_id']}. I’ve recorded this for our support team to review against our policy. A team member will follow up within 24 business hours."
    else: return ''
    return f"Hi {name},\n\n{answer}\n\nWarm regards,\nTeam Kesar"


def process_email(email, orders, faq, tickets):
    info=classify(email); sender=(email.get('from') or {}).get('email','')
    body=((email.get('subject') or '')+' '+(email.get('body') or '')).lower()
    order=get_order(orders, info.get('order_id'), sender if not info.get('order_id') else None)
    access=authorized(order,sender) if order else False
    risk_reasons=[]
    if info['confidence'] < 0.75 and info['intent'] != 'other': risk_reasons.append('Low AI confidence')
    if info['sentiment']=='angry' and info['intent'] != 'other': risk_reasons.append('Angry or highly dissatisfied customer')
    if order is not None and not access: risk_reasons.append('Order ownership could not be verified')
    if info['intent']=='return_refund': risk_reasons.append('Refund or return dispute requires authorization')
    if info['intent']=='complaint': risk_reasons.append('Complaint requires human review')
    if info['intent']=='order_status' and not order:
        risk_reasons.append('Missing or unverifiable order details')
    if any(term in body for term in ('damaged','leak','leaking','cracked','broken','missing item','wrong item')):
        risk_reasons.append('Damaged or missing product requires human review')
    faq_matches=search_faq(faq,email.get('subject','')+' '+email.get('body','')) if info['intent']=='product_query' else ''
    if info['intent']=='product_query' and not faq_matches: risk_reasons.append('No verified FAQ match')
    if any(term in body for term in ('eczema','psoriasis','pregnan','severe acne','allerg','cure','treat')):
        risk_reasons.append('Medical or allergy-related question requires human review')
    risk=bool(risk_reasons)
    needs_human=bool(risk or info['intent'] in ('return_refund','complaint'))
    draft=draft_reply(email,info,order,faq,access)
    ticket=None
    if info['intent'] in ('return_refund','complaint'):
        oid=order.get('order_id') if order and access else info.get('order_id')
        existing=next((t for t in tickets if t.get('order_id')==oid and t.get('status','Open').lower() not in ('closed','resolved')),None) if oid else None
        if existing:
            existing['notes']=(existing.get('notes','')+' | '+info['summary']).strip(' |'); existing['email_ids']=existing.get('email_ids',[])+[email.get('id')]; ticket=existing
        else:
            ticket={'ticket_id':f"TKT-{len(tickets)+1:03d}",'order_id':oid or '', 'email_ids':[email.get('id')], 'summary':info['summary'],'priority':'High' if info['intent']=='complaint' else 'Normal','status':'Open','notes':info['summary']}
            tickets.append(ticket)
    escalation_reason='; '.join(risk_reasons) if needs_human else ''
    audit={'email_id':email.get('id'),'received_at':email.get('received_at'),'from':sender,'subject':email.get('subject'),
           'intent':info['intent'],'secondary_intent':info['secondary_intent'],'order_id':info.get('order_id'),
           'sentiment':info['sentiment'],'language':info['language'],'urgency':info.get('urgency','medium'),
           'confidence':info['confidence'],'summary':info['summary'],'needs_human':needs_human,
           'draft_reply':draft,'ticket_id':ticket.get('ticket_id') if ticket else '',
           'order_authorized':access if order else None,'escalation_reason':escalation_reason,
           'classification_source':info.get('classification_source','fallback'),
           'tool_results':{'get_order': {'called': bool(order), 'authorized': access if order else None},
                           'search_faq': {'called': info['intent']=='product_query',
                                          'matched': bool(faq_matches), 'result': faq_matches[:2000]}}
          }
    return audit,ticket


def run_batch(emails, orders, faq):
    tickets=[]; audits=[]
    for email in emails:
        a,_=process_email(email,orders,faq,tickets); audits.append(a)
    return audits,tickets
