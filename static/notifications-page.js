'use strict';
(()=>{
 const list=document.getElementById('notification-page-items');
 const status=document.getElementById('notification-status');
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function render(event){
  const data=event.detail;
  status.textContent=data.unread?`${data.unread} unread · Updates automatically every 1.5 seconds.`:'All caught up · Updates automatically every 1.5 seconds.';
  list.innerHTML=data.items.length?data.items.map(item=>`<a class="notification-card ${item.seen?'':'notification-card-unread'}" href="${esc(item.link)}" data-notice="${esc(item.id)}"><span class="notification-category">${esc(item.category)}</span><strong>${esc(item.text)}</strong><time datetime="${esc(item.at)}">${esc(new Date(item.at).toLocaleString())}</time>${item.seen?'':'<span class="notification-new">New</span>'}</a>`).join(''):'<div class="notification-empty"><strong>No notifications yet</strong><p>New activity for your account will appear here.</p></div>';
 }
 window.addEventListener('ncet:notifications-updated',render);
 document.getElementById('notification-refresh').addEventListener('click',()=>window.dispatchEvent(new Event('ncet:notifications-refresh')));
})();
