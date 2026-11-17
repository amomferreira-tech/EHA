'use strict';
(() => {
  const tabs=Array.from(document.querySelectorAll('[data-detail-tab]'));
  const panels=Array.from(document.querySelectorAll('[data-detail-panel]'));
  if(!tabs.length)return;
  function select(name,focus=false){
    for(const tab of tabs){const active=tab.dataset.detailTab===name;tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;if(active&&focus)tab.focus();}
    for(const panel of panels)panel.hidden=panel.dataset.detailPanel!==name;
  }
  for(const tab of tabs){
    tab.addEventListener('click',()=>select(tab.dataset.detailTab));
    tab.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();
      const i=event.key==='Home'?0:event.key==='End'?tabs.length-1:(tabs.indexOf(tab)+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
      select(tabs[i].dataset.detailTab,true);
    });
  }
  select('people');
})();
