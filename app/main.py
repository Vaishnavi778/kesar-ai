from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
import json, io, csv, os
from .engine import get_data, run_batch, process_email
from .db import init_db, upsert_orders, upsert_customer, create_or_update_ticket, add_audit, list_tickets, get_ticket, update_ticket_status, list_audit_logs
from .sheets import sync_rows

app=Flask(__name__, template_folder='../templates', static_folder='../static')
orders, emails, faq, voice=get_data()
init_db()
upsert_orders(orders)
audits=[]; tickets=[]
if emails:
    audits,tickets=run_batch(emails,orders,faq)
    for audit in audits:
        sender=audit.get('from','')
        cid=upsert_customer(audit.get('customer_name',''),sender)
        ticket=next((x for x in tickets if x.get('ticket_id')==audit.get('ticket_id')),None)
        if ticket:
            existing_db_ticket=get_ticket(ticket['ticket_id'])
            db_status=existing_db_ticket['status'] if existing_db_ticket else ('Awaiting Human Review' if audit['needs_human'] else 'AI Processing')
            create_or_update_ticket({
                'ticket_id':ticket['ticket_id'],'customer_id':cid,'customer_name':'',
                'customer_email':sender,'email_subject':audit.get('subject',''),
                'original_message':audit.get('summary',''),'intent':audit['intent'],
                'sentiment':audit['sentiment'],'urgency':audit.get('urgency','medium'),
                'ai_response':audit['draft_reply'],'status':db_status,
                'escalation_reason':audit['escalation_reason'],'confidence':audit['confidence'],
                'tool_results':audit['tool_results']
            })
        add_audit(audit.get('ticket_id',''),audit.get('email_id',''),'Classification completed',audit)

@app.get('/')
def index():
    persisted_tickets=list_tickets()
    resolved=sum(1 for ticket in persisted_tickets if str(ticket.get('status','')).lower() in ('resolved','closed','approved'))
    escalated=sum(1 for audit in audits if audit.get('needs_human'))
    stats={'emails':len(audits),'tickets':len(persisted_tickets),'open':sum(1 for ticket in persisted_tickets if str(ticket.get('status','')).lower() not in ('resolved','closed')),
           'human':escalated,'resolved':resolved,
           'drafts':sum(1 for audit in audits if audit.get('draft_reply') and not audit.get('needs_human'))}
    return render_template('index.html',stats=stats, audits=audits, tickets=tickets, emails=emails, orders=orders)

@app.get('/api/state')
def state():
    persisted_tickets=list_tickets()
    resolved=sum(1 for ticket in persisted_tickets if str(ticket.get('status','')).lower() in ('resolved','closed','approved'))
    stats={'emails':len(audits),'tickets':len(persisted_tickets),'human':sum(a['needs_human'] for a in audits),'resolved':resolved}
    return jsonify({'stats':stats,'audits':audits,'tickets':persisted_tickets,'emails':emails})

@app.post('/api/process')
def process():
    data=request.get_json(force=True); email=data.get('email',{})
    a,t=process_email(email,orders,faq,tickets); audits.insert(0,a)
    if t and t not in tickets: tickets.append(t)
    sender=(email.get('from') or {}).get('email','')
    name=(email.get('from') or {}).get('name','')
    cid=upsert_customer(name,sender)
    if t:
        create_or_update_ticket({
            'ticket_id':t['ticket_id'],'customer_id':cid,'customer_name':name,'customer_email':sender,
            'email_subject':email.get('subject',''),'original_message':email.get('body',''),
            'intent':a['intent'],'sentiment':a['sentiment'],'urgency':a['urgency'],
            'ai_response':a['draft_reply'],'status':'Awaiting Human Review' if a['needs_human'] else 'AI Processing',
            'escalation_reason':a['escalation_reason'],'confidence':a['confidence'],'tool_results':a['tool_results']
        })
    add_audit(t.get('ticket_id') if t else '',email.get('id'),'Email received',{'subject':email.get('subject')})
    add_audit(t.get('ticket_id') if t else '',email.get('id'),'Classification completed',a)
    sheets=sync_rows(ticket_row=[
        t.get('ticket_id',''),name,sender,email.get('subject',''),a['intent'],a['sentiment'],a['urgency'],
        a['draft_reply'],'Awaiting Human Review' if a['needs_human'] else 'AI Processing',a['escalation_reason'],a['confidence']
    ] if t else None,audit_row=[
        email.get('id'),t.get('ticket_id','') if t else '',a['intent'],a['confidence'],a['escalation_reason'],a['classification_source']
    ])
    return jsonify({'audit':a,'ticket':t})

@app.post('/api/upload')
def upload():
    global orders,emails,faq,voice,audits,tickets
    files=request.files
    try:
        if 'orders' in files: orders=json.load(files['orders'])['orders']
        if 'emails' in files: emails=json.load(files['emails'])['emails']
        if 'faq' in files: faq=files['faq'].read().decode('utf-8')
        if 'voice' in files: voice=files['voice'].read().decode('utf-8')
        upsert_orders(orders)
        audits,tickets=run_batch(emails,orders,faq)
        for audit in audits:
            sender=audit.get('from','')
            cid=upsert_customer('',sender)
            ticket=next((x for x in tickets if x.get('ticket_id')==audit.get('ticket_id')),None)
            if ticket:
                existing_db_ticket=get_ticket(ticket['ticket_id'])
                db_status=existing_db_ticket['status'] if existing_db_ticket else ('Awaiting Human Review' if audit['needs_human'] else 'AI Processing')
                create_or_update_ticket({
                    'ticket_id':ticket['ticket_id'],'customer_id':cid,'customer_name':'','customer_email':sender,
                    'email_subject':audit.get('subject',''),'original_message':audit.get('summary',''),
                    'intent':audit['intent'],'sentiment':audit['sentiment'],'urgency':audit.get('urgency','medium'),
                    'ai_response':audit['draft_reply'],'status':db_status,
                    'escalation_reason':audit['escalation_reason'],'confidence':audit['confidence'],
                    'tool_results':audit['tool_results']
                })
            add_audit(audit.get('ticket_id',''),audit.get('email_id',''),'Classification completed',audit)
        return jsonify({'ok':True,'count':len(audits)})
    except Exception as e: return jsonify({'ok':False,'error':str(e)}),400

@app.get('/export/<kind>.csv')
def export(kind):
    rows=audits if kind=='audit' else tickets
    if not rows: return 'No rows',404
    out=io.StringIO(); keys=list(dict.fromkeys(k for r in rows for k in r.keys()))
    w=csv.DictWriter(out,fieldnames=keys); w.writeheader()
    for r in rows: w.writerow({k:json.dumps(r.get(k)) if isinstance(r.get(k),(dict,list)) else r.get(k,'') for k in keys})
    return app.response_class(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename=kesar_{kind}.csv'})

@app.get('/health')
def health(): return jsonify({'status':'ok','orders_loaded':len(orders),'emails_loaded':len(emails)})

@app.get('/api/tickets')
def api_tickets():
    status=request.args.get('status')
    return jsonify(list_tickets(status))

@app.get('/api/tickets/<ticket_id>')
def api_ticket(ticket_id):
    ticket=get_ticket(ticket_id)
    return jsonify(ticket) if ticket else (jsonify({'error':'Ticket not found'}),404)

@app.post('/api/tickets/<ticket_id>/approve')
def approve_ticket(ticket_id):
    data=request.get_json(silent=True) or {}
    response=data.get('response')
    ticket=get_ticket(ticket_id)
    if not ticket:
        return jsonify({'error':'Ticket not found'}),404
    update_ticket_status(ticket_id,'Approved',response)
    add_audit(ticket_id,'','Human approval',{'approved':True,'response':response})
    sync_rows(ticket_row=[ticket_id,ticket['customer_name'],ticket['customer_email'],ticket['email_subject'],
                           ticket['intent'],ticket['sentiment'],ticket['urgency'],response or ticket['ai_response'],'Approved',
                           ticket['escalation_reason'] or '',ticket['confidence']], audit_row=[
                           '',ticket_id,ticket['intent'],ticket['confidence'],'Human approval','human'])
    return jsonify(get_ticket(ticket_id))

@app.post('/api/tickets/<ticket_id>/reject')
def reject_ticket(ticket_id):
    ticket=get_ticket(ticket_id)
    if not ticket:
        return jsonify({'error':'Ticket not found'}),404
    data=request.get_json(silent=True) or {}
    reason=data.get('reason','Rejected by human agent')
    update_ticket_status(ticket_id,'Escalated',escalation_reason=reason)
    add_audit(ticket_id,'','Human rejection',{'reason':reason})
    return jsonify(get_ticket(ticket_id))

@app.post('/api/tickets/<ticket_id>/resolve')
def resolve_ticket(ticket_id):
    ticket=get_ticket(ticket_id)
    if not ticket:
        return jsonify({'error':'Ticket not found'}),404
    update_ticket_status(ticket_id,'Resolved')
    add_audit(ticket_id,'','Final status','Resolved')
    return jsonify(get_ticket(ticket_id))

@app.post('/api/tickets/<ticket_id>/regenerate')
def regenerate_ticket(ticket_id):
    ticket=get_ticket(ticket_id)
    if not ticket:
        return jsonify({'error':'Ticket not found'}),404
    original=ticket.get('original_message') or ''
    current=ticket.get('ai_response') or ''
    edited=current.strip()
    if edited:
        regenerated=edited
    elif original:
        regenerated="Hello,\n\nThank you for contacting Kesar & Co. Our support team is reviewing your request and will follow up within 24 business hours.\n\nWarm regards,\nTeam Kesar"
    else:
        regenerated=""
    update_ticket_status(ticket_id,ticket['status'],regenerated)
    add_audit(ticket_id,'','Response regenerated',{'response':regenerated})
    sync_rows(ticket_row=[ticket_id,ticket['customer_name'],ticket['customer_email'],ticket['email_subject'],
                           ticket['intent'],ticket['sentiment'],ticket['urgency'],regenerated,ticket['status'],
                           ticket['escalation_reason'] or '',ticket['confidence']])
    return jsonify(get_ticket(ticket_id))

@app.get('/api/search')
def api_search():
    query=(request.args.get('q') or '').strip().lower()
    if not query:
        return jsonify({'emails':[], 'tickets':[], 'audits':[]})
    email_matches=[]
    for audit in audits:
        searchable=' '.join(str(audit.get(k,'') or '') for k in
                            ('email_id','from','subject','summary','intent','sentiment','order_id')).lower()
        if query in searchable:
            email_matches.append(audit)
    ticket_matches=[]
    for ticket in tickets:
        searchable=' '.join(str(ticket.get(k,'') or '') for k in
                            ('ticket_id','order_id','summary','status','priority','notes')).lower()
        if query in searchable:
            ticket_matches.append(ticket)
    audit_matches=[
        row for row in list_audit_logs(100)
        if query in (str(row.get('action',''))+' '+str(row.get('details',''))).lower()
    ]
    return jsonify({'emails':email_matches[:30], 'tickets':ticket_matches[:30], 'audits':audit_matches[:30]})

@app.get('/api/analytics')
def api_analytics():
    intent_counts={}
    for audit in audits:
        intent=audit.get('intent','other')
        intent_counts[intent]=intent_counts.get(intent,0)+1
    confidence_buckets={'0.0-0.5':0,'0.5-0.75':0,'0.75-0.9':0,'0.9-1.0':0}
    for audit in audits:
        confidence=float(audit.get('confidence') or 0)
        if confidence < 0.5:
            confidence_buckets['0.0-0.5']+=1
        elif confidence < 0.75:
            confidence_buckets['0.5-0.75']+=1
        elif confidence < 0.9:
            confidence_buckets['0.75-0.9']+=1
        else:
            confidence_buckets['0.9-1.0']+=1
    persisted_tickets=list_tickets()
    resolved=sum(1 for ticket in persisted_tickets if str(ticket.get('status','')).lower() in ('resolved','closed','approved'))
    escalated=sum(1 for audit in audits if audit.get('needs_human'))
    return jsonify({
        'intent_distribution':intent_counts,
        'confidence_distribution':confidence_buckets,
        'resolution_rate':round((resolved/len(tickets)*100) if tickets else 0,1),
        'escalation_rate':round((escalated/len(audits)*100) if audits else 0,1),
        'ticket_statuses':{status:sum(1 for ticket in persisted_tickets if ticket.get('status')==status)
                           for status in sorted({ticket.get('status','Open') for ticket in persisted_tickets})},
        'processing':{'emails':len(audits),'tickets':len(persisted_tickets),'escalated':escalated,'resolved':resolved}
    })

@app.get('/api/audit')
def api_audit():
    action=request.args.get('action')
    rows=list_audit_logs()
    if action:
        rows=[row for row in rows if action.lower() in str(row.get('action','')).lower()]
    return jsonify(rows)

@app.get('/api/knowledge')
def api_knowledge():
    query=(request.args.get('q') or '').strip().lower()
    sections=[]
    current=None
    for line in faq.splitlines():
        if line.startswith('## '):
            current={'title':line[3:].strip(),'content':''}
            sections.append(current)
        elif current and line.strip():
            current['content']+=(line.strip()+'\n')
    if query:
        sections=[section for section in sections
                  if query in (section['title']+' '+section['content']).lower()]
    return jsonify({'sections':sections,'source':'data/faq.md'})

if __name__=='__main__': app.run(host='127.0.0.1',port=5000,debug=True)
