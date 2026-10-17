/* Shared NCET 1.5s shimmer. No spinning, no artificial network delays. */
(()=>{'use strict';
 const originalFetch=window.fetch.bind(window);
 let inflight=0,shown=false,timeout=null,loader=null;
 const ignore=url=>/\/api\/(alerts|notifications|auth\/me)/.test(url);
 function getLoader(){
  if(loader)return loader;
  if(!document.body)return null;
  loader=document.createElement('div');loader.className='ncet-network-loader';
  loader.setAttribute('role','status');loader.setAttribute('aria-live','polite');loader.hidden=true;
  loader.innerHTML='<img src="/static/ncet-brand.svg" width="48" height="30" alt=""><span>Working…</span>';
  document.body.append(loader);return loader;
 }
 function update(){
  if(timeout){clearTimeout(timeout);timeout=null}
  const node=getLoader();
  if(!node)return;
  if(!inflight){node.hidden=true;shown=false;return}
  if(shown)return;
  timeout=setTimeout(()=>{timeout=null;if(inflight&&getLoader()){loader.hidden=false;shown=true}},550);
 }
 window.fetch=function(...args){
  const request=args[0];
  const url=typeof request==='string'?request:request instanceof Request?request.url:String(request?.url||'');
  const opts=args[1]||{};
  const method=(opts.method||(request instanceof Request?request.method:'GET')).toUpperCase();
  const pending=/^\/(api\/|students\/)|^https?:\/\//.test(url)&&(!ignore(url))&&
   (method!=='GET'||!/(directory|sitemap)/.test(url));
  if(pending){inflight++;update()}
  try{
   return originalFetch(...args).finally(()=>{
    if(pending){inflight=Math.max(0,inflight-1);update()}
   });
  }catch(error){
   if(pending){inflight=Math.max(0,inflight-1);update()}
   throw error;
  }
 };
 window.addEventListener('pageshow',()=>{if(!inflight&&loader)loader.hidden=true});
})();
