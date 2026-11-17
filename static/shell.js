'use strict';
(() => {
  const sidebar=document.getElementById('app-sidebar'),toggle=document.querySelector('.menu-toggle'),shade=document.querySelector('.menu-shade');
  if(!sidebar||!toggle)return;
  const open=value=>{document.body.classList.toggle('menu-open',value);toggle.setAttribute('aria-expanded',String(value));toggle.setAttribute('aria-label',value?'Fechar menu':'Abrir menu');if(shade)shade.hidden=!value;};
  toggle.addEventListener('click',()=>open(toggle.getAttribute('aria-expanded')!=='true'));
  shade?.addEventListener('click',()=>open(false));
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){open(false);toggle.focus();}});
})();
