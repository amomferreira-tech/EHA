'use strict';
(() => {
  const sidebar=document.getElementById('app-sidebar'),toggle=document.querySelector('.menu-toggle'),shade=document.querySelector('.menu-shade');
  if(!sidebar||!toggle)return;
  const mobile=window.matchMedia('(max-width:760px)');
  const key='eha-live-sidebar-hidden';
  let collapsed=false,mobileOpen=false;
  try{collapsed=localStorage.getItem(key)==='1';}catch(_){}
  function paint(){
    const visible=mobile.matches?mobileOpen:!collapsed;
    document.body.classList.toggle('menu-collapsed',collapsed);
    document.body.classList.toggle('menu-open',mobile.matches&&mobileOpen);
    toggle.setAttribute('aria-expanded',String(visible));
    toggle.setAttribute('aria-label',visible?'Ocultar menu lateral':'Mostrar menu lateral');
    toggle.title=visible?'Ocultar menu lateral':'Mostrar menu lateral';
    sidebar.inert=!visible;
    sidebar.setAttribute('aria-hidden',String(!visible));
    if(shade)shade.hidden=!(mobile.matches&&mobileOpen);
  }
  function close(){
    if(mobile.matches)mobileOpen=false;
    else{collapsed=true;try{localStorage.setItem(key,'1');}catch(_){}}
    paint();
  }
  toggle.addEventListener('click',()=>{
    if(mobile.matches)mobileOpen=!mobileOpen;
    else{collapsed=!collapsed;try{localStorage.setItem(key,collapsed?'1':'0');}catch(_){}}
    paint();
  });
  shade?.addEventListener('click',close);
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&(mobileOpen||sidebar.contains(document.activeElement))){close();toggle.focus();}
  });
  mobile.addEventListener('change',()=>{mobileOpen=false;paint();});
  paint();
})();
