/* Progressive enhancement for the one-page student portfolio. */
(()=>{
'use strict';
const nav=document.querySelector('.resume-anchors');
if(!nav)return;
const links=[...nav.querySelectorAll('a[href^="#"]')];
const sections=links.map(link=>document.getElementById(decodeURIComponent(link.hash.slice(1))));
if(!links.length||sections.some(section=>!section))return;
const setCurrent=id=>{
 for(const link of links){
  if(link.hash==='#'+id)link.setAttribute('aria-current','location');
  else link.removeAttribute('aria-current');
 }
};
const currentHash=()=>decodeURIComponent(location.hash.slice(1));
if(sections.some(section=>section.id===currentHash()))setCurrent(currentHash());
else setCurrent(sections[0].id);
window.addEventListener('hashchange',()=>{
 const id=currentHash();
 if(sections.some(section=>section.id===id))setCurrent(id);
});
if('IntersectionObserver' in window){
 const observer=new IntersectionObserver(entries=>{
  const visible=entries.filter(entry=>entry.isIntersecting)
    .sort((a,b)=>b.intersectionRatio-a.intersectionRatio)[0];
  if(visible)setCurrent(visible.target.id);
 },{rootMargin:'-18% 0px -68% 0px',threshold:[0,.15,.4]});
 sections.forEach(section=>observer.observe(section));
}
})();

