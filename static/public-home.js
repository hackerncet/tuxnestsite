'use strict';
const stage=document.getElementById('logo-stage');const button=document.getElementById('toggle-animation');
button?.addEventListener('click',()=>{const paused=stage.classList.toggle('paused');button.textContent=paused?'Play motion':'Pause motion';button.setAttribute('aria-pressed',String(paused));});
