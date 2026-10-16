'use strict';
const $=id=>document.getElementById(id);const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let csrf='',role='',selected=null;
function show(id,yes){$(id).classList.toggle('hidden',!yes)}
function notify(t,error=false){$('alert').textContent=t;$('alert').className=error?'error':'success'}
async function api(url,options={}){const headers={...(options.headers||{})};if(options.method&&options.method!=='GET')headers['X-CSRF-Token']=csrf;const r=await fetch(url,{credentials:'same-origin',cache:'no-store',...options,headers});const data=await r.json().catch(()=>({}));if(!r.ok){let d=data.detail;if(Array.isArray(d))d=d.map(e=>e.msg).join(', ');throw new Error(typeof d==='string'?d:'Request unsuccessful.')}return data}
function download(name,content){const blob=new Blob([content],{type:'text/csv;charset=utf-8'});const a=document.createElement('a');const u=URL.createObjectURL(blob);a.href=u;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000)}
const csvCell=t=>'"'+String(t).replaceAll('"','""')+'"';
$('template').addEventListener('click',()=>download('NCET_BCA_student_import_template.csv','usn,full_name,semester\r\n'));
async function init(){try{let r=await api('/api/auth/me');csrf=r.csrf;role=r.user.role;if(!['staff','hod','admin'].includes(role))throw Error('Not authorized');await loadRoster();$('staff-name').textContent=r.user.name;show('desk',true);if(role==='hod'){show('hod-queue',true);await loadCases()}}catch(e){show('denied',true);notify('Sign in with an authorized BCA faculty account.',true)}}
function downloadCredentials(x){const rows=['usn,full_name,semester,temporary_password',...x.credentials.map(c=>[c.usn,c.name,c.semester,c.temporary_password].map(csvCell).join(','))];download('NCET_BCA_ONETIME_credentials.csv',rows.join('\r\n')+'\r\n');}
async function loadRoster(){let r=await api('/api/bca/students');$('roster').innerHTML=r.items.length?r.items.map(x=>`<div class="entry"><div class="row"><strong>${esc(x.name)}</strong><span class="small muted">${esc(x.usn)} · Semester ${esc(x.semester)}</span></div><details><summary>Edit student details</summary><form class="edit-student-form" data-usn="${esc(x.usn)}"><label>Full name <input name="full_name" value="${esc(x.name==='Registration pending'?'':x.name)}" minlength="3" maxlength="130" required></label><label>Semester <input name="semester" type="number" min="1" max="8" value="${esc(x.semester)}" required></label><button class="btn" type="submit">Save details</button></form></details></div>`).join(''):'<p class="muted">No students enrolled yet.</p>'}
$('import-form').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);let btn=e.target.querySelector('button[type=submit]');btn.disabled=true;try{let file=f.get('file');let endpoint=file?.name.toLowerCase().endsWith('.xlsx')?'/api/bca/students/import-excel':'/api/bca/students/import';let x=await api(endpoint,{method:'POST',body:f});downloadCredentials(x);notify(`${x.created} students enrolled. The one-time credentials file has been downloaded. Store it securely.`);e.target.reset();await loadRoster()}catch(err){notify(err.message,true)}finally{btn.disabled=false}});
async function loadCases(){try{let r=await api('/api/bca/cases');$('cases').innerHTML=r.items.length?r.items.map(x=>`<button class="entry" type="button" data-case="${esc(x.reference)}"><span class="row"><strong>${esc(x.subject)}</strong><span class="status ${esc(x.status)}">${esc(x.status.replaceAll('_',' '))}</span></span><span class="muted small">${esc(x.reference)} · ${esc(x.category)}</span></button>`).join(''):'<p class="muted">No cases awaiting review.</p>';for(const b of $('cases').querySelectorAll('[data-case]'))b.addEventListener('click',()=>openCase(b.dataset.case))}catch(err){notify(err.message,true)}}
async function openCase(ref){try{const d=await api('/api/bca/cases/'+encodeURIComponent(ref));selected=ref;show('selected-case',true);$('case-title').textContent=d.subject;$('case-details').innerHTML=`<p class="muted small">${esc(d.reference)} · ${esc(d.student?.name)} · ${esc(d.student?.usn)} · ${esc(d.status.replaceAll('_',' '))}</p><p>${esc(d.description)}</p><h3>Replies</h3>${d.messages.map(m=>`<div class="thread"><strong>${esc(m.author)}</strong><span class="muted small"> ${esc(new Date(m.created_at).toLocaleString())}</span><p>${esc(m.body)}</p></div>`).join('')||'<p class="muted">No replies yet.</p>'}`;show('case-update',d.status!=='closed');show('message-form',d.status!=='closed');$('selected-case').scrollIntoView({behavior:'smooth'})}catch(err){notify(err.message,true)}}
$('close-case').addEventListener('click',()=>{selected=null;show('selected-case',false)});
$('case-update').addEventListener('submit',async e=>{e.preventDefault();if(!selected)return;const body=Object.fromEntries(new FormData(e.target));try{await api('/api/bca/cases/'+encodeURIComponent(selected)+'/status',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});notify('Case status updated.');e.target.reset();await openCase(selected);await loadCases()}catch(err){notify(err.message,true)}});
$('message-form').addEventListener('submit',async e=>{e.preventDefault();if(!selected)return;try{await api('/api/bca/cases/'+encodeURIComponent(selected)+'/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:new FormData(e.target).get('message')})});e.target.reset();notify('Reply sent.');await openCase(selected)}catch(err){notify(err.message,true)}});
$('logout').addEventListener('click',async()=>{try{await api('/api/auth/logout',{method:'POST'})}catch{}location.replace('/app')});
init();

$('quick-enroll').addEventListener('submit',async e=>{
 e.preventDefault();
 const lines=$('enroll-list').value.split(/[\n;]+/).map(s=>s.trim()).filter(Boolean);
 if(!lines.length||lines.length>100)return notify('Enter between 1 and 100 students.',true);
 const records=[];
 for(const line of lines){
  const parts=line.split(',').map(v=>v.trim());
  if(parts.length===1){records.push({usn:parts[0],full_name:'',semester:1});continue;}
  if(parts.length!==2&&parts.length!==3)return notify('Each line should contain USN, optional name, optional semester.',true);
  records.push({usn:parts[0],full_name:parts[1]||'',semester:Number(parts[2]||1)});
 }
 const button=e.target.querySelector('button[type=submit]');button.disabled=true;
 try{
  const result=await api('/api/bca/students/enroll',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({students:records})});
  downloadCredentials(result);notify(result.created+' USNs registered. Share credentials privately; students must change their passwords.');
  e.target.reset();await loadRoster();
 }catch(err){notify(err.message,true)}finally{button.disabled=false}
});
$('roster').addEventListener('submit',async e=>{
 const form=e.target.closest('.edit-student-form');if(!form)return;e.preventDefault();
 const data=new FormData(form);
 try{
  await api('/api/bca/students/'+encodeURIComponent(form.dataset.usn),{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({full_name:data.get('full_name'),semester:Number(data.get('semester'))})});
  notify('Student details updated. If a public profile existed, the student must republish it.');await loadRoster();
 }catch(err){notify(err.message,true)}
});
