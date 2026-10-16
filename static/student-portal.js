'use strict';
let csrf='', selected=null;
const $=id=>document.getElementById(id);
const escapeHtml=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function show(id,yes){$(id).classList.toggle('hidden',!yes)}
function notify(text,error=false){$('alert').className=error?'error':'success';$('alert').textContent=text;$('alert').classList.remove('hidden')}
async function api(url,opts={}){const headers={...(opts.headers||{})};if(csrf&&opts.method&&opts.method!=='GET')headers['X-CSRF-Token']=csrf;let response=await fetch(url,{credentials:'same-origin',cache:'no-store',...opts,headers});let body=await response.json().catch(()=>({}));if(!response.ok){let detail=body.detail;if(Array.isArray(detail))detail=detail.map(x=>x.msg).join('; ');throw new Error(typeof detail==='string'?detail:'Request failed. Try again.')}return body}
async function start(){try{const me=await api('/api/auth/me');if(me.user.role!=='student')throw new Error('Use a registered BCA student account.');csrf=me.csrf;let profile=await api('/api/bca/me');$('who').textContent=profile.usn+' · Semester '+profile.semester;show('sign-in',false);show('logout',true);show('change-password',profile.must_change_password);show('workspace',!profile.must_change_password);if(!profile.must_change_password){await loadCases();await loadShowcase()}}catch{show('sign-in',true);show('workspace',false);show('change-password',false);show('logout',false)}}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();let fd=new FormData(e.target);let usn=String(fd.get('usn')||'').trim().toLowerCase();try{let login=await api('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:usn,password:fd.get('password'),role:'student'})});if(login.user.role!=='student')throw new Error('Not a student account.');csrf=login.csrf;e.target.reset();notify('Signed in.');await start()}catch(err){notify(err.message,true);$('login-password').value=''}});
$('logout').addEventListener('click',async()=>{try{await api('/api/auth/logout',{method:'POST'})}catch{}csrf='';selected=null;location.replace('/students/portal')});
$('password-form').addEventListener('submit',async e=>{e.preventDefault();const fd=new FormData(e.target);const button=e.target.querySelector('button[type=submit]');button.disabled=true;button.setAttribute('aria-busy','true');try{await api('/api/auth/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_password:fd.get('old_password'),new_password:fd.get('new_password')})});e.target.reset();notify('Password updated. You can now submit requests.');await start()}catch(err){notify(err.message,true)}finally{button.disabled=false;button.removeAttribute('aria-busy')}});
async function loadCases(){try{let x=await api('/api/bca/cases');$('case-list').innerHTML=x.items.map(item=>`<button type="button" class="entry" data-ref="${escapeHtml(item.reference)}"><span class="row"><strong>${escapeHtml(item.subject)}</strong><span class="status ${escapeHtml(item.status)}">${escapeHtml(item.status.replaceAll('_',' '))}</span></span><span class="small muted">${escapeHtml(item.reference)} · ${escapeHtml(new Date(item.created_at).toLocaleDateString())}</span></button>`).join('')||'<p class="muted">No requests yet. Start with the form.</p>';for(const btn of $('case-list').querySelectorAll('[data-ref]'))btn.addEventListener('click',()=>openCase(btn.dataset.ref));}catch(err){notify(err.message,true)}}
$('new-case').addEventListener('submit',async e=>{e.preventDefault();let data=Object.fromEntries(new FormData(e.target));let button=e.target.querySelector('button[type=submit]');button.disabled=true;button.setAttribute('aria-busy','true');try{let result=await api('/api/bca/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});notify(`Request ${result.reference} submitted to the BCA HOD.`);e.target.reset();await loadCases();await openCase(result.reference)}catch(err){notify(err.message,true)}finally{button.disabled=false;button.removeAttribute('aria-busy')}});
async function openCase(ref){try{let c=await api('/api/bca/cases/'+encodeURIComponent(ref));selected=ref;show('case-detail',true);$('case-heading').textContent=c.subject;$('case-info').innerHTML=`<p><span class="status ${escapeHtml(c.status)}">${escapeHtml(c.status.replaceAll('_',' '))}</span> <span class="muted small">${escapeHtml(ref)} · ${escapeHtml(c.category)}</span></p><p>${escapeHtml(c.description)}</p><h3>Conversation</h3>${c.messages.map(m=>`<div class="thread"><strong>${escapeHtml(m.author)}</strong> <span class="small muted">${escapeHtml(new Date(m.created_at).toLocaleString())}</span><p>${escapeHtml(m.body)}</p></div>`).join('')||'<p class="muted">No replies yet.</p>'}`;show('message-form',c.status!=='closed');$('case-detail').scrollIntoView({behavior:'smooth'});}catch(err){notify(err.message,true)}}
$('close-case').addEventListener('click',()=>{show('case-detail',false);selected=null});
$('message-form').addEventListener('submit',async e=>{e.preventDefault();if(!selected)return;try{await api('/api/bca/cases/'+encodeURIComponent(selected)+'/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:new FormData(e.target).get('message')})});e.target.reset();notify('Reply sent.');await openCase(selected)}catch(err){notify(err.message,true)}});
start();

async function loadShowcase(){
 try{
  const p=await api('/api/bca/showcase/me');
  $('showcase-name').value=p.full_name;
  $('showcase-mobile').value=p.mobile;
  $('showcase-email').value=p.email;
  $('showcase-about').value=p.about;
  $('showcase-skills').value=p.skills.join(', ');
  $('showcase-certs').value=p.certificates.map(c=>[c.title,c.issuer,c.proof_url].join(' | ')).join('\n');
  $('showcase-public').checked=p.published;
  show('my-public-profile',p.published);
  $('my-public-profile').href='/students/profile/'+encodeURIComponent(p.usn);
 }catch(err){notify(err.message,true)}
}
$('showcase-form').addEventListener('submit',async e=>{
 e.preventDefault();
 const skills=$('showcase-skills').value.split(',').map(s=>s.trim()).filter(Boolean);
 const certText=$('showcase-certs').value.trim();
 const certificates=[];
 if(certText){
  for(const line of certText.split('\n')){
   if(!line.trim())continue;
   const parts=line.split('|').map(s=>s.trim());
   if(parts.length!==3)return notify('Each certificate requires title | issuer | public HTTPS URL.',true);
   certificates.push({title:parts[0],issuer:parts[1],proof_url:parts[2]});
  }
 }
 const body={full_name:$('showcase-name').value,mobile:$('showcase-mobile').value,
  email:$('showcase-email').value,about:$('showcase-about').value,
  skills,certificates,publish:$('showcase-public').checked};
 const btn=e.target.querySelector('button[type=submit]');btn.disabled=true;
 try{
  const response=await api('/api/bca/showcase/me',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  notify(response.published?'Public profile published. Private contact information is hidden.':'Profile saved privately.');
  await loadShowcase();
 }catch(err){notify(err.message,true)}finally{btn.disabled=false}
});
