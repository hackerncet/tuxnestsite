'use strict';
// Authenticated notification inbox. Refreshes every 1.5 seconds while visible.
(()=>{
 const container=document.createElement('aside');container.id='ncet-alerts';container.hidden=true;
 container.innerHTML='<button id="alert-toggle" type="button" aria-expanded="false" aria-controls="alert-list">Notifications <span id="alert-count" aria-live="polite"></span></button><section id="alert-list" role="region" aria-label="In-app notifications" hidden><h2>Notifications</h2><div id="alert-items" aria-live="polite">Loading…</div><a class="alert-inbox-link" href="/notifications">Open full inbox</a><button id="alert-close" type="button">Close</button></section>';
 document.body.append(container);
 const toggle=container.querySelector('#alert-toggle'),panel=container.querySelector('#alert-list'),list=container.querySelector('#alert-items'),badge=container.querySelector('#alert-count');
 const esc=v=>String(v??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
 const POLL_MS=1500;
 const REQUEST_TIMEOUT_MS=60000;
 let csrf='',running=false;
 function open(show){panel.hidden=!show;toggle.setAttribute('aria-expanded',String(show));}
 toggle.addEventListener('click',()=>{open(panel.hidden);if(!panel.hidden)refresh()});
 container.querySelector('#alert-close').addEventListener('click',()=>open(false));
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){open(false)}});
 async function refresh(){
  if(running||document.visibilityState==='hidden')return;running=true;
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),REQUEST_TIMEOUT_MS);
  try{
   const response=await fetch('/api/alerts/inbox',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
   if(!response.ok){container.hidden=true;return}
   const result=await response.json();csrf=result.csrf||csrf;
   window.dispatchEvent(new CustomEvent('ncet:notifications-updated',{detail:result}));
   container.hidden=false;badge.textContent=result.unread?'('+result.unread+' new)':'';
   list.innerHTML=result.items.length?result.items.map(n=>'<a class="alert-entry '+(n.seen?'':'alert-unread')+'" href="'+esc(n.link)+'" data-notice="'+esc(n.id)+'"><span>'+esc(n.category)+'</span><strong>'+esc(n.text)+'</strong><small>'+esc(new Date(n.at).toLocaleString())+'</small></a>').join(''):'<p>No new activity yet.</p>';
  }catch(e){if(!container.hidden)list.textContent='Notifications could not be refreshed.'}
  finally{clearTimeout(timeout);running=false}
 }
 container.addEventListener('click',e=>{
  const link=e.target.closest('[data-notice]');if(!link)return;
  fetch('/api/alerts/'+encodeURIComponent(link.dataset.notice)+'/read',{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':csrf},keepalive:true}).then(()=>refresh()).catch(()=>{});
 });
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')refresh()});
 window.addEventListener('ncet:notifications-refresh',refresh);
 window.addEventListener('focus',refresh);
 setInterval(refresh,POLL_MS);
 refresh();
})();
