const $=s=>document.querySelector(s);
document.querySelectorAll('.filter').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('.email-row').forEach(r=>{const f=b.dataset.filter;r.style.display=(f==='all'||(f==='needs'&&r.dataset.needs==='yes')||r.dataset.intent===f)?'':'none'})}));
function showEmail(id){const a=window.KESAR_AUDITS.find(x=>x.email_id===id);const e=window.KESAR_EMAILS.find(x=>x.id===id);if(!a)return;const esc=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const ticket=a.ticket_id?`<div style="display:flex;gap:8px;margin-top:12px"><button class="btn primary" id="approveReply" type="button">Approve</button><button class="btn secondary" id="rejectReply" type="button">Reject</button></div>`:'';$('#detailContent').innerHTML=`<div class="modalhead"><div><h2>${esc(a.subject)}</h2><p>${esc(a.from)} · ${esc(a.email_id)}</p></div></div><p style="font-size:11px;color:#626b5d;line-height:1.7;white-space:pre-wrap;margin-bottom:15px">${esc(e?.body||a.summary)}</p><div style="display:flex;gap:7px;margin-bottom:15px"><span class="tag ${esc(a.intent)}">${esc(a.intent.replaceAll('_',' '))}</span><span class="tag ${a.needs_human?'review':'ready'}">${a.needs_human?'Needs human review':'Draft ready'}</span><span class="tag other">Confidence ${(a.confidence*100).toFixed(0)}%</span></div><h3 style="font:700 12px Manrope;margin-bottom:8px">Copilot draft</h3><textarea id="replyEditor" rows="7" style="white-space:pre-wrap">${esc(a.draft_reply||'No reply draft generated for this email.')}</textarea><p style="font-size:9px;color:#999;margin-top:10px">Order access authorized: ${a.order_authorized===null?'Not applicable':a.order_authorized?'Yes':'No'} · Ticket: ${esc(a.ticket_id||'None')} · Tool calls: ${esc(JSON.stringify(a.tool_results||{}))}</p>${a.escalation_reason?`<p style="font-size:10px;color:#9a7a3e;margin-top:8px">Escalation: ${esc(a.escalation_reason)}</p>`:''}${ticket}`;$('#detailModal').showModal();if(a.ticket_id){$('#approveReply').addEventListener('click',async()=>{await fetch(`/api/tickets/${encodeURIComponent(a.ticket_id)}/approve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({response:$('#replyEditor').value})});location.reload()});$('#rejectReply').addEventListener('click',async()=>{await fetch(`/api/tickets/${encodeURIComponent(a.ticket_id)}/reject`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:'Rejected after human review'})});location.reload()})}}
$('#uploadForm').addEventListener('submit',async e=>{e.preventDefault();const msg=$('#uploadMsg');msg.textContent='Importing and processing…';try{const r=await fetch('/api/upload',{method:'POST',body:new FormData(e.target)});const d=await r.json();if(!r.ok)throw Error(d.error);msg.textContent=`Imported successfully. ${d.count} emails processed.`;setTimeout(()=>location.reload(),900)}catch(err){msg.textContent='Import failed: '+err.message}});
$('#processForm').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);const email={id:'MAN-'+Date.now(),received_at:new Date().toISOString(),from:{name:f.get('name'),email:f.get('sender')},subject:f.get('subject'),body:f.get('body')};const msg=$('#processMsg');msg.textContent='Processing…';try{const r=await fetch('/api/process',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});const d=await r.json();msg.textContent='Processed. Reloading dashboard…';setTimeout(()=>location.reload(),700)}catch(err){msg.textContent='Could not process email: '+err.message}});

document.querySelectorAll('.filter').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  const f=b.dataset.filter;
  document.querySelectorAll('.email-row').forEach(row=>{
    const matches=f==='all'
      ||(f==='needs'&&row.dataset.needs==='yes')
      ||(f==='urgent'&&row.dataset.urgency==='high')
      ||(f==='draft-ready'&&row.dataset.needs==='no')
      ||row.dataset.intent===f;
    row.style.display=matches?'':'none';
  });
}));

async function showTicket(ticketId){
  const response=await fetch(`/api/tickets/${encodeURIComponent(ticketId)}`);
  if(!response.ok){return;}
  const ticket=await response.json();
  const esc=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  $('#detailContent').innerHTML=`<div class="modalhead"><div><h2>${esc(ticket.ticket_id)}</h2><p>${esc(ticket.customer_email)} · ${esc(ticket.email_subject)}</p></div></div>
    <div style="display:flex;gap:7px;margin-bottom:15px"><span class="tag ${esc(ticket.intent)}">${esc(ticket.intent?.replaceAll('_',' '))}</span><span class="tag review">${esc(ticket.status)}</span><span class="tag other">Confidence ${(Number(ticket.confidence||0)*100).toFixed(0)}%</span></div>
    <h3>Original request</h3><p class="detail-copy">${esc(ticket.original_message)}</p>
    <h3>AI response editor</h3><textarea id="ticketReplyEditor" rows="7">${esc(ticket.ai_response)}</textarea>
    ${ticket.escalation_reason?`<p class="escalation-copy">Escalation: ${esc(ticket.escalation_reason)}</p>`:''}
    <div class="detail-actions"><button class="btn primary" id="ticketApprove" type="button">Approve</button><button class="btn secondary" id="ticketRegenerate" type="button">Regenerate</button><button class="btn secondary" id="ticketReject" type="button">Reject</button><button class="btn secondary" id="ticketResolve" type="button">Resolve</button></div>`;
  $('#detailModal').showModal();
  $('#ticketApprove').addEventListener('click',async()=>{
    await fetch(`/api/tickets/${encodeURIComponent(ticketId)}/approve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({response:$('#ticketReplyEditor').value})});
    location.reload();
  });
  $('#ticketRegenerate').addEventListener('click',async()=>{
    await fetch(`/api/tickets/${encodeURIComponent(ticketId)}/regenerate`,{method:'POST'});
    location.reload();
  });
  $('#ticketReject').addEventListener('click',async()=>{
    await fetch(`/api/tickets/${encodeURIComponent(ticketId)}/reject`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:'Rejected after human review'})});
    location.reload();
  });
  $('#ticketResolve').addEventListener('click',async()=>{
    await fetch(`/api/tickets/${encodeURIComponent(ticketId)}/resolve`,{method:'POST'});
    location.reload();
  });
}

document.querySelectorAll('.ticketline[data-ticket-id]').forEach(row=>{
  row.addEventListener('click',()=>showTicket(row.dataset.ticketId));
  row.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' ')showTicket(row.dataset.ticketId)});
});

async function refreshAnalytics(){
  const response=await fetch('/api/analytics');
  if(!response.ok)return;
  const data=await response.json();
  $('#resolutionRate').textContent=`${data.resolution_rate}%`;
  $('#escalationRate').textContent=`${data.escalation_rate}%`;
  $('#analyticsTickets').textContent=data.processing.tickets;
  $('#analyticsEmails').textContent=data.processing.emails;
}
$('#refreshAnalytics')?.addEventListener('click',refreshAnalytics);
refreshAnalytics();

async function loadAudit(){
  const response=await fetch('/api/audit');
  if(!response.ok)return;
  const rows=await response.json();
  const container=$('#auditTable');
  if(!container)return;
  container.innerHTML=rows.slice(0,30).map(row=>{
    const details=typeof row.details==='string'?row.details:'';
    return `<div class="audit-row"><b>${String(row.action||'')}</b><span>${String(row.ticket_id||'—')}</span><small>${String(row.created_at||'')}</small><p>${details.length>180?details.slice(0,180)+'…':details}</p></div>`;
  }).join('')||'<div class="empty">No audit events recorded.</div>';
}
loadAudit();

async function searchKnowledge(){
  const query=$('#knowledgeQuery').value.trim();
  const response=await fetch(`/api/knowledge?q=${encodeURIComponent(query)}`);
  if(!response.ok)return;
  const data=await response.json();
  $('#knowledgeResults').innerHTML=data.sections.map(section=>`<article class="knowledge-card"><h3>${section.title}</h3><pre>${section.content}</pre></article>`).join('')||'<div class="empty">No FAQ sections match this search.</div>';
}
$('#knowledgeSearchButton')?.addEventListener('click',searchKnowledge);
$('#knowledgeQuery')?.addEventListener('keydown',event=>{if(event.key==='Enter')searchKnowledge()});
searchKnowledge();

async function globalSearch(){
  const query=$('#globalSearchInput').value.trim();
  if(!query){$('#globalSearchResults').innerHTML='<div class="empty">Enter an order ID, customer email, subject or ticket ID.</div>';return;}
  const response=await fetch(`/api/search?q=${encodeURIComponent(query)}`);
  if(!response.ok)return;
  const data=await response.json();
  const esc=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const emails=data.emails.map(a=>`<button type="button" class="search-result" data-email-id="${esc(a.email_id)}"><b>${esc(a.subject)}</b><span>${esc(a.from)} · ${esc(a.intent)}</span></button>`).join('');
  const tickets=data.tickets.map(t=>`<button type="button" class="search-result" data-ticket-id="${esc(t.ticket_id)}"><b>${esc(t.ticket_id)}</b><span>${esc(t.summary)} · ${esc(t.status)}</span></button>`).join('');
  $('#globalSearchResults').innerHTML=(emails+tickets)||'<div class="empty">No matching emails or tickets.</div>';
  $('#globalSearchResults').querySelectorAll('[data-email-id]').forEach(button=>button.addEventListener('click',()=>{document.getElementById('searchModal').close();showEmail(button.dataset.emailId)}));
  $('#globalSearchResults').querySelectorAll('[data-ticket-id]').forEach(button=>button.addEventListener('click',()=>{document.getElementById('searchModal').close();showTicket(button.dataset.ticketId)}));
}
$('#globalSearchButton')?.addEventListener('click',()=>{document.getElementById('searchModal').showModal();setTimeout(()=>$('#globalSearchInput').focus(),50)});
$('#globalSearchInput')?.addEventListener('input',globalSearch);

$('#notificationButton')?.addEventListener('click',()=>{
  document.querySelector('[data-filter="needs"]')?.click();
  document.getElementById('inbox').scrollIntoView({behavior:'smooth'});
});
$('#profileButton')?.addEventListener('click',()=>{
  $('#detailContent').innerHTML='<div class="modalhead"><div><h2>Kesar Support</h2><p>Administrator</p></div></div><p class="detail-copy">Human-review operator for Kesar & Co. customer support.</p>';
  $('#detailModal').showModal();
});
