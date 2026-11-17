'use strict';
const $=id=>document.getElementById(id);
const fmt=n=>new Intl.NumberFormat('pt-BR').format(n);
const pct=n=>(n*100).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stationName=s=>String(s).replace(/^SoC_/i,'').replaceAll('_',' · ');
const stationCode=s=>catalog?.station_codes?.[s]||'';
const short=s=>stationCode(s)||stationName(s);
const stationText=s=>stationCode(s)?stationCode(s)+' · '+stationName(s):s;
const norm=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replaceAll('_',' ');
const NETWORK_HOURS=Array.from({length:24},(_,i)=>(i+6)%24);
let HOURS=[...NETWORK_HOURS];
const hourDay=h=>h<(current?.schedule?.starts[0]??6)?'D+1':'D0';
const hourLabel=h=>String(h).padStart(2,'0')+'h '+hourDay(h);
let view='overall',current=null,selectedHour=null,peopleLimit=100,version=0,catalog=null,operatorStation='',selectedShift='';
const expandedOperators=new Set();
async function api(url){const r=await fetch(url);if(r.status===401){location.href='/login';throw Error('Sua sessão expirou.');}const d=await r.json();if(!r.ok)throw Error(d.error||'Não foi possível consultar os dados.');return d;}
function options(select,values,first){const previous=select.value;select.replaceChildren();for(const [value,label] of [['',first],...values.map(v=>[v,select.id==='soc'?stationText(v):v])]){const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option);}select.value=values.includes(previous)?previous:'';select.dispatchEvent(new Event('optionsupdated'));}
function saveLocation(push=false){const p=new URLSearchParams({view,day:$('day').value,period:$('period').value});if($('soc').value)p.set('soc',$('soc').value);if(view==='soc'){if($('flow').value)p.set('flow',$('flow').value);if($('reason').value)p.set('reason',$('reason').value);if(selectedHour!==null)p.set('hour',selectedHour);if(selectedShift)p.set('shift',selectedShift);}history[push?'pushState':'replaceState']({},'',location.pathname+'?'+p);}
function setView(next,push=true){const stationSelected=!!$('soc').value;view=stationSelected?'soc':next;$('view-tabs').hidden=true;$('detail-switcher').hidden=!stationSelected;$('unit-nav').hidden=true;$('settings-link').href='/settings'+(stationSelected?'?soc='+encodeURIComponent($('soc').value):'');$('production-link').href='/?view=soc&soc='+encodeURIComponent($('soc').value);const settingsNav=document.querySelector('[data-side-settings]');if(settingsNav)settingsNav.href='/settings'+(stationSelected?'?soc='+encodeURIComponent($('soc').value):'');const unitNav=document.querySelector('[data-side-view="soc"]');if(unitNav)unitNav.href='/soc'+(stationSelected?'?soc='+encodeURIComponent($('soc').value):'');for(const link of document.querySelectorAll('[data-side-view]')){const active=link.dataset.sideView===view;link.classList.toggle('active',active);if(active)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}for(const name of ['overall','soc']){const selected=name===view;$('tab-'+name).setAttribute('aria-selected',String(selected));$('tab-'+name).tabIndex=selected?0:-1;$('view-'+name).hidden=!selected;}if(stationSelected){for(const id of ['matrix-head','matrix-body','matrix-foot'])$(id).replaceChildren();$('overall-bips').textContent='—';$('soc-count').textContent='—';}for(const id of ['soc-filter','flow-filter','reason-filter'])$(id).hidden=view!=='soc';$('pick-soc').hidden=stationSelected;$('soc-content').hidden=!stationSelected;peopleLimit=100;current=null;$('error').hidden=true;saveLocation(push);load();}
function syncStatus(sync){const stamp=sync.last_success?new Date(sync.last_success).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',dateStyle:'short',timeStyle:'short'}):'nenhuma coleta';$('sync').textContent=(sync.failed?'Falha na coleta · ':sync.stale?'Atualização pendente · ':'Última coleta · ')+stamp+' · Coleta horária no minuto '+String(sync.collection_minute??20).padStart(2,'0');$('sync').className=sync.failed||sync.stale?'warning':'good';if(sync.failed&&sync.error){$('error').textContent=sync.error;$('error').hidden=false;}}
function paintNetwork(){
  if(!current||current.view!=='overall')return;
  $('matrix-head').closest('table').classList.toggle('period-matrix',(current.period?.kind||'day')!=='day');
  if((current.period?.kind||'day')!=='day'){paintPeriodNetwork();return;}
  const q=norm($('network-search').value);const rows=current.matrix.filter(r=>norm(r.soc+' '+short(r.soc)).includes(q));
  $('overall-bips').textContent=fmt(current.bips);$('soc-count').textContent=fmt(current.active_socs);$('network-hours').textContent=current.coverage.length+' de 24 '+(current.period?.kind==='day'?'horas':'faixas horárias')+' com registros salvos';
  $('matrix-head').innerHTML='<tr><th>UNIDADE</th><th>TOTAL BIPS</th>'+NETWORK_HOURS.map(h=>`<th>${String(h).padStart(2,'0')}h<small class="day-marker">${h<6?'D+1':'D0'}</small></th>`).join('')+'</tr>';
  const max=Math.max(1,...rows.flatMap(r=>r.hours.filter(n=>n!==null)));
  $('matrix-body').innerHTML=rows.map(r=>`<tr><td><button class="soc-link" data-soc="${esc(r.soc)}">${esc(short(r.soc))}<span>${esc(stationCode(r.soc)?stationName(r.soc):'Ver detalhe ↗')}</span></button></td><td>${r.hours.some(n=>n!==null)?fmt(r.bips):'—'}</td>${NETWORK_HOURS.map(h=>{const n=r.hours[h];return `<td ${n===null?'':`style="background:rgba(238,77,45,${.025+.2*n/max})"`}>${n===null?'—':fmt(n)}</td>`;}).join('')}</tr>`).join('');
  const total=rows.reduce((n,r)=>n+r.bips,0);
  const hours=NETWORK_HOURS.map(h=>{const values=rows.map(r=>r.hours[h]).filter(n=>n!==null);return values.length?fmt(values.reduce((a,b)=>a+b,0)):'—';});
  $('matrix-foot').innerHTML=rows.length?`<tr><td>${q?'TOTAL DO FILTRO':'TOTAL GERAL'}</td><td>${fmt(total)}</td>${hours.map(v=>`<td>${v}</td>`).join('')}</tr>`:'';
  $('network-empty').hidden=rows.length>0;$('network-empty').textContent=q?'Nenhuma estação encontrada.':'Nenhum SOC foi encontrado no histórico.';
}
function paintHourChart(series){
  const max=Math.max(1,...series.map(r=>r.bips));
  const byHour=new Map(series.map(r=>[r.hour,r]));const shiftHours=current?.schedule?.shifts.find(s=>s.id===selectedShift)?.hours;const boundaries=new Set(current?.schedule?.shifts.map(s=>s.start)||[]);
  $('chart').innerHTML=HOURS.map(h=>byHour.get(h)).map(r=>`<button class="hour-bar ${r.observed?'':'missing'} ${selectedHour===r.hour?'selected':''} ${shiftHours&&!shiftHours.includes(r.hour)?'outside-shift':''} ${boundaries.has(r.hour)?'turn-start':''}" data-hour="${r.hour}" aria-label="${hourLabel(r.hour)}: ${r.observed?fmt(r.bips)+' bips':'sem registro'}" aria-pressed="${selectedHour===r.hour}" title="${hourLabel(r.hour)} · ${r.observed?fmt(r.bips)+' bips':'sem registro'}"><b class="${r.bips/max*160>=26?'in-bar':'above-bar'}" style="bottom:${40+Math.max(2,r.bips/max*160)+(r.bips/max*160>=26?-20:5)}px">${r.observed?fmt(r.bips):''}</b><i style="height:${r.observed?Math.max(2,r.bips/max*160):2}px"></i><span>${String(r.hour).padStart(2,'0')}<small class="day-marker">${hourDay(r.hour)}</small></span></button>`).join('');
}
function paintPareto(rows,total){
  if(!rows.length||!total){$('pareto-chart').innerHTML='<p class="no-data">Sem bips para compor o Pareto neste recorte.</p>';$('pareto-key').replaceChildren();$('pareto-insight').textContent='Sem volume no recorte';return;}
  const n=rows.length,W=Math.max(720,n*64+100),H=270,left=48,right=48,top=24,base=220,step=(W-left-right)/n;
  const max=Math.max(...rows.map(r=>r.bips));
  let chart=`<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Pareto dos motivos de tratativa: barras de bips e linha de participação acumulada"><line x1="${left}" y1="${base}" x2="${W-right}" y2="${base}" stroke="#e8dcd3"/>`;
  for(const fraction of [0,.5,1]){const y=base-(base-top)*fraction;chart+=`<text x="${W-right+10}" y="${y+4}" class="axis-label">${fraction*100}%</text>`;}
  const threshold=base-(base-top)*.8;chart+=`<line x1="${left}" y1="${threshold}" x2="${W-right}" y2="${threshold}" stroke="#d2b9a9" stroke-dasharray="5 5"/>`;
  rows.forEach((r,i)=>{const x=left+step*i+step*.17,w=step*.66,y=base-(base-top)*r.bips/max;chart+=`<rect x="${x}" y="${y}" width="${w}" height="${base-y}" rx="4" fill="${i===0?'#ee4d2d':'#ff9d79'}"><title>${esc(r.name)}: ${fmt(r.bips)} bips · ${pct(r.share)} · acumulado ${pct(r.cumulative)}</title></rect><text x="${x+w/2}" y="${Math.max(15,y-8)}" text-anchor="middle" class="bar-value">${fmt(r.bips)}</text><text x="${x+w/2}" y="${base+22}" text-anchor="middle" class="axis-label">${i+1}</text>`;});
  const points=rows.map((r,i)=>`${left+step*(i+.5)},${base-(base-top)*r.cumulative}`).join(' ');chart+=`<polyline points="${points}" fill="none" stroke="#286b68" stroke-width="2.5"/>`;
  rows.forEach((r,i)=>{chart+=`<circle cx="${left+step*(i+.5)}" cy="${base-(base-top)*r.cumulative}" r="4" fill="#286b68"><title>${esc(r.name)} · acumulado ${pct(r.cumulative)}</title></circle>`;});
  $('pareto-chart').innerHTML=chart+'</svg>';
  $('pareto-key').innerHTML=rows.map((r,i)=>`<button class="pareto-label" data-reason="${esc(r.name)}" title="Filtrar este motivo"><b>${i+1}</b><span>${esc(r.name)}</span><strong>${pct(r.share)}</strong></button>`).join('');
  const count=rows.findIndex(r=>r.cumulative>=.8)+1;$('pareto-insight').textContent=`${count} ${count===1?'motivo concentra':'motivos concentram'} ${pct(rows[count-1].cumulative)} dos bips`;
}
function miniHours(hours){return '<div class="mini-hours">'+HOURS.map(h=>({h,n:hours[h]})).map(({n,h})=>n>0?`<span><small>${hourLabel(h)}</small><b>${fmt(n)}</b></span>`:'').join('')+'</div>';}
function paintReasons(rows){$('reason-count').textContent=rows.length+' motivos';$('reason-rows').innerHTML=rows.map(r=>`<tr><td><details class="reason-detail"><summary>${esc(r.name)}</summary><p>${fmt(r.operators)} colaboradores com registro</p>${(current.period?.kind||'day')!=='day'?miniPeriodValues(r.period_values):miniHours(r.hours)}</details></td><td>${fmt(r.bips)}</td><td>${fmt(r.shipments)}</td><td>${pct(r.share)}</td><td>${pct(r.cumulative)}</td></tr>`).join('')||'<tr><td colspan="5">Sem registros neste recorte.</td></tr>';}
function paintPeople(){
  if(!current||current.view!=='soc')return;
  $('people-head').closest('table').classList.toggle('period-matrix',(current.period?.kind||'day')!=='day');
  if((current.period?.kind||'day')!=='day'){paintPeriodPeople();return;}
  if(operatorStation!==current.soc){expandedOperators.clear();operatorStation=current.soc;}
  const q=norm($('search').value),rows=current.people.filter(p=>norm(p.name).includes(q));
  const observed=new Set(current.coverage.map(r=>r.hour));
  const shiftHours=current.schedule?.shifts.find(s=>s.id===selectedShift)?.hours||HOURS;
  const visibleHours=new Set(shiftHours.filter(h=>selectedHour===null||h===selectedHour));
  const cell=(hours,h)=>observed.has(h)&&visibleHours.has(h)?fmt(hours[h]||0):'—';
  $('people-head').innerHTML='<tr><th scope="col">OPERADOR</th><th scope="col">TOTAL BIPS</th>'+HOURS.map(h=>`<th scope="col"><button class="operator-hour" data-hour="${h}" aria-label="Filtrar ${hourLabel(h)}">${String(h).padStart(2,'0')}h<small class="day-marker">${hourDay(h)}</small><small>${observed.has(h)?'SALVO':'SEM REGISTRO'}</small></button></th>`).join('')+'</tr>';
  const totals=Array(24).fill(0);rows.forEach(p=>p.hours.forEach((n,h)=>totals[h]+=n));
  const bips=rows.reduce((n,p)=>n+p.bips,0),shipments=rows.reduce((n,p)=>n+p.shipments,0);
  $('people-total').textContent=fmt(bips)+' bips · '+fmt(shipments)+' pacotes';
  const overall=`<tr class="operator-overall"><td>${q?'TOTAL DO FILTRO':'TOTAL DO SOC'}</td><td>${fmt(bips)}</td>${HOURS.map(h=>`<td>${cell(totals,h)}</td>`).join('')}</tr>`;
  $('people-list').innerHTML=overall+rows.slice(0,peopleLimit).map(p=>{
    const expanded=expandedOperators.has(p.name);
    const main=`<tr class="operator-row"><td><button class="operator-toggle" data-operator="${esc(p.name)}" aria-expanded="${expanded}"><span class="expand-symbol">${expanded?'−':'+'}</span><span>${esc(p.name)}</span></button></td><td class="operator-total"><strong>${fmt(p.bips)}</strong><small>${fmt(p.shipments)} pacotes</small></td>${HOURS.map(h=>`<td title="${h}h · ${observed.has(h)&&visibleHours.has(h)?fmt(p.shipment_hours?.[h]||0)+' pacotes':'sem observação neste recorte'}">${cell(p.hours,h)}</td>`).join('')}</tr>`;
    const reasons=expanded?p.reasons.map(r=>`<tr class="operator-reason"><td>↳ ${esc(r.name)}</td><td><strong>${fmt(r.bips)}</strong><small>${fmt(r.shipments)} pacotes</small></td>${HOURS.map(h=>`<td>${cell(r.hours,h)}</td>`).join('')}</tr>`).join(''):'';
    return main+reasons;
  }).join('')+(rows.length?'':'<tr><td colspan="26" class="no-data">Nenhum operador neste recorte.</td></tr>');
  $('more').hidden=rows.length<=peopleLimit;
}
function paintShiftControls(data){
  const definition=data.schedule,first=definition.hour_order[0],last=definition.hour_order[23];
  const hh=h=>String(h).padStart(2,'0')+'h';
  $('hour-range').textContent=hh(first)+' D0 → '+hh(last)+(first===0?' D0':' D+1')+(definition.configured?' · Do início do T1 à última hora do T3':' · Ordem padrão, configure os turnos da unidade')+(data.period?.kind!=='day'?' · Horas acumuladas do período':'');
  if(data.period?.kind!=='day')$('hour-range').textContent=periodDate(data.period.start)+' a '+periodDate(data.period.end)+(data.period.kind==='month'?' · Semanas do mês':' · Segunda a domingo');
  $('schedule-note').hidden=definition.configured;
  $('schedule-note').innerHTML='Horários ainda não definidos para este SOC. <a href="/settings?soc='+encodeURIComponent(data.soc)+'">Configurar T1, T2 e T3</a>.';
  $('shift-tabs').innerHTML=definition.configured?`<button data-shift="" aria-pressed="${!selectedShift}">${data.period?.kind==='week'?'Semana completa':data.period?.kind==='month'?'Mês completo':'Dia completo'}<small>${hh(first)} → ${hh(last)}</small></button>`+definition.shifts.map(s=>`<button data-shift="${s.id}" aria-pressed="${selectedShift===s.id}">${s.name}<small>${hh(s.start)}–${hh(s.end)}</small></button>`).join(''):'';
  $('shift-summary').innerHTML=data.shift_totals.map(s=>`<div><b>${s.name} · ${hh(s.start)}–${hh(s.end)}</b><strong>${fmt(s.bips)} bips</strong><span>${fmt(s.shipments)} pacotes · ${s.observed_hours}/${s.hours.length} horas com registro</span></div>`).join('');
}
function paintSoc(data){
  HOURS=data.schedule.hour_order;selectedShift=data.shift||'';paintShiftControls(data);
  $('soc-content').hidden=false;$('pick-soc').hidden=true;$('soc-title').textContent=short(data.soc);$('scope').textContent=short(data.soc)+' · somente esta estação';
  const period=selectedHour===null?(selectedShift?selectedShift.toUpperCase()+' · Turno selecionado':(data.period?.kind==='week'?'Semana completa':data.period?.kind==='month'?'Mês completo':'Dia completo')):hourLabel(selectedHour)+' · Hora selecionada';$('detail-period').textContent=period;$('hour-caption').textContent=period;$('bips-caption').textContent=period;
  $('bips').textContent=fmt(data.bips);$('shipments').textContent=fmt(data.shipments);$('operators').textContent=fmt(data.operators);$('saved-hours').textContent=fmt(data.preserved_hours??data.coverage.length)+'/'+fmt(data.possible_hours||24);$('saved-range').textContent=data.coverage.length?(data.period?.kind==='day'?'Do dia operacional selecionado':'Horas salvas no período'):'Aguardando a primeira observação';$('empty').hidden=data.series.some(r=>r.observed);$('clear-hour').hidden=selectedHour===null;
  options($('flow'),data.available_flows,'Todos os fluxos');options($('reason'),data.available_reasons,'Todos os motivos');
  paintProductionChart(data);paintPareto(data.reasons,data.bips);paintReasons(data.reasons);paintPeople();
  $('flows').innerHTML=data.flows.map(r=>`<div class="reason"><div class="reason-line"><span>${esc(r.name)}</span><b>${fmt(r.bips)} · ${pct(data.bips?r.bips/data.bips:0)}</b></div><div class="track"><i style="width:${data.bips?r.bips/data.bips*100:0}%"></i></div></div>`).join('')||'<p class="no-data">Sem fluxo registrado.</p>';
  $('flow-summary').textContent=`${fmt(data.bips)} bips · ${fmt(data.shipments)} pacotes no recorte`;
  const coverage=new Map(data.coverage.map(r=>[r.hour,r]));$('coverage').innerHTML=HOURS.map(h=>`<span class="${coverage.has(h)?'saved':''}" title="${coverage.has(h)?'Hora preservada. Última observação: '+new Date(coverage.get(h).last_seen).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'}):'Sem observação salva'}">${String(h).padStart(2,'0')}h ${hourDay(h)}</span>`).join('');
}
async function load(){
  const requestVersion=++version;if(!$('day').value)return;
  if(view==='soc'&&!$('soc').value){$('scope').textContent='Escolha uma estação';$('sync').textContent='Aguardando seleção do SOC';$('pick-soc').hidden=false;$('soc-content').hidden=true;$('refresh').disabled=false;return;}
  $('refresh').disabled=true;$('error').hidden=true;$('period-panel').hidden=true;$('sync').textContent='Atualizando o recorte…';
  if(view==='soc'){$('soc-content').hidden=true;$('pick-soc').hidden=true;}
  const p=new URLSearchParams({view,day:$('day').value,period:$('period').value});if(view==='soc'){p.set('soc',$('soc').value);p.set('flow',$('flow').value);p.set('reason',$('reason').value);if(selectedHour!==null)p.set('hour',selectedHour);if(selectedShift)p.set('shift',selectedShift);}
  try{const data=await api('/api/dashboard?'+p);if(requestVersion!==version)return;current=data;catalog.station_codes=data.station_codes||catalog.station_codes||{};paintPeriod(data);syncStatus(data.sync);if(view==='overall'){$('scope').textContent='Todos os SOCs · '+(data.period?.kind==='week'?'Processado por dia':data.period?.kind==='month'?'Processado por semana':'Processado H/H');paintNetwork();}else paintSoc(data);}
  catch(e){if(requestVersion!==version)return;current=null;$('error').textContent=e.message;$('error').hidden=false;$('sync').textContent='Atualização não concluída';if(view==='soc'){$('soc-content').hidden=true;$('pick-soc').hidden=false;}}
  finally{if(requestVersion===version)$('refresh').disabled=false;}
}
async function init(){
  try{catalog=await api('/api/catalog');options($('soc'),catalog.stations,'Escolha um SOC');const p=new URLSearchParams(location.search),station=document.querySelector('[data-station]').dataset.station;
    $('soc').value=catalog.stations.includes(p.get('soc'))?p.get('soc'):location.pathname==='/network'?'':catalog.stations.includes(station)?station:'';$('soc').dispatchEvent(new Event('change'));
    $('period').value=['day','week','month'].includes(p.get('period'))?p.get('period'):'day';
    $('day').value=/^\d{4}-\d{2}-\d{2}$/.test(p.get('day')||'')?p.get('day'):catalog.days[0]||new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    // Os filtros de motivo e fluxo são sempre derivados apenas da estação escolhida.
    if(p.get('flow'))options($('flow'),[p.get('flow')],'Todos os fluxos');$('flow').value=p.get('flow')||'';
    if(p.get('reason'))options($('reason'),[p.get('reason')],'Todos os motivos');$('reason').value=p.get('reason')||'';
    selectedShift=p.get('shift')||'';const h=p.get('hour');selectedHour=h!==null&&/^\d+$/.test(h)&&Number(h)<24?Number(h):null;
    view=location.pathname==='/network'?'overall':location.pathname==='/soc'?'soc':p.get('view')==='overall'?'overall':p.get('view')==='soc'?'soc':$('soc').value?'soc':'overall';setView(view,false);
  }catch(e){$('error').textContent=e.message;$('error').hidden=false;}
}
for(const name of ['overall','soc']){$('tab-'+name).addEventListener('click',()=>setView(name));$('tab-'+name).addEventListener('keydown',e=>{if(['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?'overall':e.key==='End'?'soc':name==='overall'?'soc':'overall';setView(next);$('tab-'+next).focus();}});}
for(const id of ['day','soc','period'])$(id).addEventListener('change',()=>{selectedHour=null;selectedShift='';peopleLimit=100;options($('flow'),[],'Todos os fluxos');options($('reason'),[],'Todos os motivos');if(id==='soc'){setView($('soc').value?'soc':'overall');return;}if(!$('day').value)return;saveLocation();load();});
for(const id of ['flow','reason'])$(id).addEventListener('change',()=>{peopleLimit=100;saveLocation();load();});
$('shift-tabs').addEventListener('click',e=>{const button=e.target.closest('[data-shift]');if(button){selectedShift=button.dataset.shift;selectedHour=null;peopleLimit=100;saveLocation();load();}});
$('refresh').addEventListener('click',load);$('network-search').addEventListener('input',paintNetwork);
$('matrix-body').addEventListener('click',e=>{const b=e.target.closest('[data-soc]');if(b){$('soc').value=b.dataset.soc;$('soc').dispatchEvent(new Event('change'));}});
$('chart').addEventListener('click',e=>{const b=e.target.closest('[data-hour]');if(b){const h=Number(b.dataset.hour);selectedShift='';selectedHour=selectedHour===h?null:h;peopleLimit=100;saveLocation();load();}});
$('clear-hour').addEventListener('click',()=>{selectedHour=null;saveLocation();load();});
$('pareto-key').addEventListener('click',e=>{const b=e.target.closest('[data-reason]');if(b){$('reason').value=b.dataset.reason;saveLocation();load();}});
$('people-list').addEventListener('click',e=>{const b=e.target.closest('[data-operator]');if(b){const name=b.dataset.operator;if(expandedOperators.has(name))expandedOperators.delete(name);else expandedOperators.add(name);paintPeople();}});
$('people-head').addEventListener('click',e=>{const b=e.target.closest('[data-hour]');if(b){const h=Number(b.dataset.hour);selectedShift='';selectedHour=selectedHour===h?null:h;saveLocation();load();}});
$('search').addEventListener('input',()=>{peopleLimit=100;paintPeople();});$('more').addEventListener('click',()=>{peopleLimit+=100;paintPeople();});
window.addEventListener('popstate',()=>init());setInterval(()=>{if(!document.hidden)load();},60000);init();
