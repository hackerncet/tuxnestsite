'use strict';
(()=>{
 const share=document.getElementById('resume-share');
 const print=document.getElementById('resume-print');
 const status=document.getElementById('resume-action-status');
 if(!share||!print||!status)return;
 const announce=text=>{status.textContent=text};
 async function copyProfileLink(url){
  if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(url);return true}
  const field=document.createElement('textarea');
  field.value=url;field.setAttribute('readonly','');field.style.position='fixed';field.style.opacity='0';
  document.body.append(field);field.select();
  let copied=false;try{copied=document.execCommand('copy')}catch{}
  field.remove();return copied;
 }
 share.addEventListener('click',async()=>{
  share.disabled=true;
  try{
   const url=new URL(share.dataset.shareUrl,location.origin).href;
   if(await copyProfileLink(url)){announce('Portfolio link copied. Share it with your network.');return}
   if(navigator.share){await navigator.share({title:document.title,url});announce('Portfolio ready to share.')}
   else announce('Copy the portfolio link from your browser address bar.');
  }catch(error){announce(error?.name==='AbortError'?'Sharing cancelled.':'Could not share right now. Copy the link from your browser address bar.')}
  finally{share.disabled=false}
 });
 print.addEventListener('click',()=>window.print());
})();
