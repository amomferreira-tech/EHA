'use strict';
// Mantém o select original como fonte do formulário e dos eventos de filtro.
for(const select of document.querySelectorAll('select[data-searchable]')){
  const wrapper=document.createElement('div');wrapper.className='searchable-select';
  select.before(wrapper);wrapper.append(select);
  const input=document.createElement('input');input.type='text';input.id=select.id+'-search';
  input.autocomplete='off';input.spellcheck=false;input.placeholder='Digite para buscar a estação…';
  input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');
  input.setAttribute('aria-expanded','false');input.setAttribute('aria-haspopup','listbox');
  const list=document.createElement('div');list.className='station-options';list.id=select.id+'-options';
  list.setAttribute('role','listbox');list.hidden=true;input.setAttribute('aria-controls',list.id);
  const label=document.querySelector('label[for="'+select.id+'"]');
  if(label){label.htmlFor=input.id;list.setAttribute('aria-label',label.textContent);}
  wrapper.append(input,list);select.hidden=true;
  let matches=[],active=-1;
  const normalize=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[_·]+/g,' ').replace(/\s+/g,' ').trim();
  const selectedText=()=>select.selectedOptions[0]?.textContent||'';
  const close=()=>{list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');};
  const sync=()=>{input.value=selectedText();};
  function highlight(index){
    active=index;
    for(const [i,button] of [...list.querySelectorAll('[role="option"]')].entries()){
      button.classList.toggle('highlighted',i===active);
      if(i===active){input.setAttribute('aria-activedescendant',button.id);button.scrollIntoView({block:'nearest'});}
    }
  }
  function choose(index){
    if(!matches[index])return;
    select.value=matches[index].value;sync();close();
    select.dispatchEvent(new Event('change',{bubbles:true}));input.focus();close();
  }
  function open(query=''){
    const q=normalize(query);matches=[...select.options].filter(o=>!o.disabled&&normalize(o.textContent).includes(q));
    list.replaceChildren();active=-1;input.removeAttribute('aria-activedescendant');
    matches.forEach((option,i)=>{
      const item=document.createElement('button');item.type='button';item.tabIndex=-1;
      item.id=list.id+'-'+i;item.setAttribute('role','option');
      item.setAttribute('aria-selected',String(option.value===select.value));item.textContent=option.textContent;
      item.addEventListener('pointerdown',e=>e.preventDefault());
      item.addEventListener('click',()=>choose(i));list.append(item);
    });
    if(!matches.length){const empty=document.createElement('p');empty.className='station-no-match';empty.textContent='Nenhuma estação encontrada.';list.append(empty);}
    list.hidden=false;input.setAttribute('aria-expanded','true');
  }
  input.addEventListener('focus',()=>{input.select();open();});
  input.addEventListener('click',()=>{if(list.hidden)open();});
  input.addEventListener('input',()=>open(input.value));
  input.addEventListener('keydown',e=>{
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){
      e.preventDefault();if(list.hidden)open(input.value===selectedText()?'':input.value);
      if(matches.length)highlight((active+(e.key==='ArrowDown'?1:active<0?0:-1)+matches.length)%matches.length);
    }else if(e.key==='Enter'){
      if(!list.hidden){e.preventDefault();if(matches.length)choose(active<0?0:active);}
    }else if(e.key==='Escape'){e.preventDefault();sync();close();}
  });
  input.addEventListener('blur',()=>{sync();close();});
  select.addEventListener('change',sync);
  new MutationObserver(()=>{if(document.activeElement!==input)sync();else open(input.value===selectedText()?'':input.value);}).observe(select,{childList:true,subtree:true});
  sync();
}
