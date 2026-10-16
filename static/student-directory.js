'use strict';
const $=id=>document.getElementById(id);
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function loadDirectory(q=''){
  $('directory-status').textContent='Searching profiles…';
  try{
    const response=await fetch('/api/bca/directory?'+new URLSearchParams({q,limit:'40'}),{credentials:'omit'});
    if(!response.ok)throw Error('The student directory is temporarily unavailable.');
    const data=await response.json();const items=data.items||[];
    $('directory-results').innerHTML=items.map(p=>`<article class="profile-card"><h2><a href="/students/profile/${encodeURIComponent(p.usn)}">${escapeHtml(p.name)}</a></h2><p><strong>${escapeHtml(p.usn)}</strong> · ${escapeHtml(p.department)}</p><p>${p.skills?.length?'Skills: '+p.skills.slice(0,5).map(escapeHtml).join(', '):'View student portfolio'}</p><a class="btn" href="/students/profile/${encodeURIComponent(p.usn)}">View profile</a></article>`).join('');
    $('directory-status').textContent=items.length?`Showing ${items.length} published profiles`:'No published profiles match this search.';
  }catch(e){$('directory-results').replaceChildren();$('directory-status').textContent=e.message}
}
$('search-profiles').addEventListener('submit',e=>{e.preventDefault();loadDirectory($('student-search').value.trim())});
$('clear-search').addEventListener('click',()=>{$('student-search').value='';loadDirectory()});
const query=new URLSearchParams(location.search).get('q')||'';$('student-search').value=query.slice(0,60);loadDirectory(query.slice(0,60));
