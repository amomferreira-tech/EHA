'use strict';
const $=id=>document.getElementById(id);
const fmt=n=>new Intl.NumberFormat('pt-BR').format(n);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const short=s=>String(s).replace(/^SoC_/i,'').replaceAll('_',' · ');
let current=null, detailData=null, selectedHour=null, peopleLimit=30, loadVersion=0, detailVersion=0;
async function api(url){const r=await fetch(url);if(r.status===401){location.href='/login';throw Error('Sua sessão expirou.');}const d=await r.json();if(!r.ok)throw Error(d.error||'Não foi possível carregar os dados.');return d;}
function option(select,values){for(const v of values){const o=document.createElement('option');o.value=v;o.textContent=v;select.append(o);}}
function paint(data){
  current=data;
  $('bips').textContent=fmt(data.bips);$('shipments').textContent=fmt(data.shipments);$('operators').textContent=fmt(data.operators);
  $('peak').textContent=data.peak?String(data.peak.hour).padStart(2,'0')+'h':'—';
  $('peak-caption').textContent=data.peak?fmt(data.peak.bips)+' bips realizados':'Sem observações no recorte';
  $('empty').hidden=data.series.some(r=>r.observed);
  $('scope').textContent=$('soc').value?short($('soc').value):'Todos os SOCs · Visão da rede';
  const sync=data.sync, stamp=sync.last_success?new Date(sync.last_success).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',dateStyle:'short',timeStyle:'short'}):'nenhuma coleta';
  $('sync').textContent=(sync.failed?'Falha na coleta · ':sync.stale?'Atualização pendente · ':'Última coleta · ')+stamp;
  $('sync').className=sync.failed||sync.stale?'warning':'good';
  const max=Math.max(1,...data.series.map(r=>r.bips));
  $('chart').innerHTML=data.series.map(r=>`<button class="hour-bar ${r.observed?'':'missing'} ${selectedHour===r.hour?'selected':''}" data-hour="${r.hour}" aria-label="${r.hour} horas: ${r.observed?fmt(r.bips)+' bips':'sem registro'}" title="${r.hour}h · ${r.observed?fmt(r.bips)+' bips':'Sem registro'}" aria-pressed="${selectedHour===r.hour}"><b>${r.observed&&r.bips>0?fmt(r.bips):''}</b><i style="height:${r.observed?Math.max(2,r.bips/max*155):2}px"></i><span>${String(r.hour).padStart(2,'0')}</span></button>`).join('');
  $('matrix-head').innerHTML='<tr><th>ESTAÇÃO</th><th>TOTAL BIPS</th>'+Array.from({length:24},(_,h)=>`<th>${String(h).padStart(2,'0')}h</th>`).join('')+'</tr>';
  const cellMax=Math.max(1,...data.matrix.flatMap(r=>r.hours.filter(v=>v!==null)));
  $('matrix-body').innerHTML=data.matrix.map(r=>`<tr><td><a href="#overview" data-soc="${esc(r.soc)}">${esc(short(r.soc))}</a></td><td>${r.hours.some(n=>n!==null)?fmt(r.bips):'—'}</td>${r.hours.map(n=>`<td ${n===null?'':`style="background:rgba(243,105,62,${.035+.19*n/cellMax})"`}>${n===null?'—':fmt(n)}</td>`).join('')}</tr>`).join('');
  $('soc-count').textContent=data.matrix.length+' estações';
  paintPeople();paintReasons(data.reasons);
}
function paintPeople(){
  if(!current)return;
  const q=$('search').value.toLocaleLowerCase('pt-BR');
  const rows=(detailData||current).people.filter(p=>p.name.toLocaleLowerCase('pt-BR').includes(q));
  $('hour-caption').textContent=selectedHour===null?'Dia completo':String(selectedHour).padStart(2,'0')+'h · Hora selecionada';
  $('people-list').innerHTML=rows.slice(0,peopleLimit).map((p,i)=>`<details class="person"><summary><span class="rank">${String(i+1).padStart(2,'0')}</span><span class="avatar">${esc(p.name.replace(/^\[[^\]]*\]/,'').trim().split(/\s+/).slice(0,2).map(s=>s[0]||'').join('').toUpperCase())}</span><span class="person-name"><b>${esc(p.name)}</b><small>${esc(short(p.soc))}</small></span><span class="person-total"><b>${fmt(p.bips)}</b><small>bips · ${fmt(p.shipments)} pacotes</small></span></summary><div class="person-detail"><h3>MOTIVOS · ${selectedHour===null?'DIA COMPLETO':selectedHour+'H'}</h3>${p.reasons.map(r=>`<div class="detail-reason"><span>${esc(r.name)}</span><b>${fmt(r.bips)} bips</b></div>`).join('')}</div></details>`).join('')||'<p class="no-data">Nenhum colaborador neste recorte.</p>';
  $('more').hidden=rows.length<=peopleLimit;
}
function paintReasons(rows){const total=rows.reduce((n,r)=>n+r.bips,0);$('reasons').innerHTML=rows.slice(0,30).map(r=>`<div class="reason"><div class="reason-line"><span>${esc(r.name)}</span><b>${fmt(r.bips)} <span class="muted">· ${total?(r.bips/total*100).toFixed(1).replace('.',','):0}%</span></b></div><div class="track"><i style="width:${total?r.bips/total*100:0}%"></i></div></div>`).join('')||'<p class="no-data">Sem motivos registrados neste recorte.</p>';}
function params(){return new URLSearchParams({day:$('day').value,soc:$('soc').value,flow:$('flow').value,subarea:$('subarea').value});}
async function detailHour(){
  if(!current)return;
  const version=++detailVersion;
  if(selectedHour===null){detailData=null;paintPeople();paintReasons(current.reasons);return;}
  const p=params();p.set('hour',selectedHour);
  const result=await api('/api/dashboard?'+p);
  if(version!==detailVersion)return;
  detailData=result;paintPeople();paintReasons(result.reasons);
}
async function load(){
  if(!$('day').value)return;
  const version=++loadVersion;++detailVersion;detailData=null;
  $('refresh').disabled=true;$('error').hidden=true;
  try{const data=await api('/api/dashboard?'+params());if(version!==loadVersion)return;paint(data);await detailHour();}
  catch(e){if(version!==loadVersion)return;$('error').textContent=e.message;$('error').hidden=false;$('sync').textContent='Atualização não concluída · resultados anteriores podem estar visíveis';$('sync').className='warning';}
  finally{if(version===loadVersion)$('refresh').disabled=false;}
}
async function chooseHour(h){selectedHour=selectedHour===h?null:h;peopleLimit=30;$('clear-hour').hidden=selectedHour===null;for(const b of $('chart').querySelectorAll('button')){b.classList.toggle('selected',Number(b.dataset.hour)===selectedHour);b.setAttribute('aria-pressed',String(Number(b.dataset.hour)===selectedHour));}try{await detailHour();}catch(e){$('error').textContent=e.message;$('error').hidden=false;}}
async function init(){
  try{const cat=await api('/api/catalog');option($('soc'),cat.stations);option($('flow'),cat.flows);option($('subarea'),cat.subareas);
    const station=document.querySelector('[data-station]').dataset.station;if(station!=='*'&&cat.stations.includes(station))$('soc').value=station;
    $('day').value=cat.days[0]||new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    await load();
  }catch(e){$('error').textContent=e.message;$('error').hidden=false;}
}
for(const id of ['day','soc','flow','subarea'])$(id).addEventListener('change',()=>{selectedHour=null;peopleLimit=30;$('clear-hour').hidden=true;load();});
$('refresh').addEventListener('click',load);
$('chart').addEventListener('click',e=>{const b=e.target.closest('[data-hour]');if(b)chooseHour(Number(b.dataset.hour));});
$('clear-hour').addEventListener('click',()=>{if(selectedHour!==null)chooseHour(selectedHour);});
$('matrix-body').addEventListener('click',e=>{const a=e.target.closest('[data-soc]');if(a){$('soc').value=a.dataset.soc;selectedHour=null;$('clear-hour').hidden=true;peopleLimit=30;load();}});
$('search').addEventListener('input',()=>{peopleLimit=30;paintPeople();});
$('more').addEventListener('click',()=>{peopleLimit+=30;paintPeople();});
setInterval(()=>{if(!document.hidden)load();},60000);
init();
