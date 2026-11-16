'use strict';
const $=id=>document.getElementById(id);
const fmt=n=>new Intl.NumberFormat('pt-BR').format(n);
const pct=n=>(n*100).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const short=s=>String(s).replace(/^SoC_/i,'').replaceAll('_',' · ');
const norm=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replaceAll('_',' ');
let view='overall',current=null,selectedHour=null,peopleLimit=25,version=0,catalog=null;
async function api(url){const r=await fetch(url);if(r.status===401){location.href='/login';throw Error('Sua sessão expirou.');}const d=await r.json();if(!r.ok)throw Error(d.error||'Não foi possível consultar os dados.');return d;}
function options(select,values,first){const previous=select.value;select.replaceChildren();for(const [value,label] of [['',first],...values.map(v=>[v,v])]){const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option);}select.value=values.includes(previous)?previous:'';select.dispatchEvent(new Event('optionsupdated'));}
function saveLocation(push=false){const p=new URLSearchParams({view,day:$('day').value});if($('soc').value)p.set('soc',$('soc').value);if(view==='soc'){if($('flow').value)p.set('flow',$('flow').value);if($('reason').value)p.set('reason',$('reason').value);if(selectedHour!==null)p.set('hour',selectedHour);}history[push?'pushState':'replaceState']({},'',location.pathname+'?'+p);}
function setView(next,push=true){view=next;for(const name of ['overall','soc']){const selected=name===view;$('tab-'+name).setAttribute('aria-selected',String(selected));$('tab-'+name).tabIndex=selected?0:-1;$('view-'+name).hidden=!selected;}for(const id of ['soc-filter','flow-filter','reason-filter'])$(id).hidden=view!=='soc';$('pick-soc').hidden=!!$('soc').value;$('soc-content').hidden=!$('soc').value;peopleLimit=25;current=null;$('error').hidden=true;saveLocation(push);load();}
function syncStatus(sync){const stamp=sync.last_success?new Date(sync.last_success).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',dateStyle:'short',timeStyle:'short'}):'nenhuma coleta';$('sync').textContent=(sync.failed?'Falha na coleta · ':sync.stale?'Atualização pendente · ':'Última coleta · ')+stamp;$('sync').className=sync.failed||sync.stale?'warning':'good';if(sync.failed&&sync.error){$('error').textContent=sync.error;$('error').hidden=false;}}
function paintNetwork(){
  if(!current||current.view!=='overall')return;
  const q=norm($('network-search').value);const rows=current.matrix.filter(r=>norm(r.soc).includes(q));
  $('overall-bips').textContent=fmt(current.bips);$('soc-count').textContent=fmt(current.active_socs);$('network-hours').textContent=current.coverage.length+' de 24 horas com registros salvos';
  $('matrix-head').innerHTML='<tr><th>ESTAÇÃO</th><th>TOTAL BIPS</th>'+Array.from({length:24},(_,h)=>`<th>${String(h).padStart(2,'0')}h</th>`).join('')+'</tr>';
  const max=Math.max(1,...rows.flatMap(r=>r.hours.filter(n=>n!==null)));
  $('matrix-body').innerHTML=rows.map(r=>`<tr><td><button class="soc-link" data-soc="${esc(r.soc)}">${esc(short(r.soc))}<span>Ver detalhe ↗</span></button></td><td>${r.hours.some(n=>n!==null)?fmt(r.bips):'—'}</td>${r.hours.map(n=>`<td ${n===null?'':`style="background:rgba(238,77,45,${.025+.2*n/max})"`}>${n===null?'—':fmt(n)}</td>`).join('')}</tr>`).join('');
  const total=rows.reduce((n,r)=>n+r.bips,0);
  const hours=Array.from({length:24},(_,h)=>{const values=rows.map(r=>r.hours[h]).filter(n=>n!==null);return values.length?fmt(values.reduce((a,b)=>a+b,0)):'—';});
  $('matrix-foot').innerHTML=rows.length?`<tr><td>${q?'TOTAL DO FILTRO':'TOTAL DA REDE'}</td><td>${fmt(total)}</td>${hours.map(v=>`<td>${v}</td>`).join('')}</tr>`:'';
  $('network-empty').hidden=rows.length>0;$('network-empty').textContent=q?'Nenhuma estação encontrada.':'Nenhum SOC foi encontrado no histórico.';
}
function paintHourChart(series){
  const max=Math.max(1,...series.map(r=>r.bips));
  $('chart').innerHTML=series.map(r=>`<button class="hour-bar ${r.observed?'':'missing'} ${selectedHour===r.hour?'selected':''}" data-hour="${r.hour}" aria-label="${r.hour} horas: ${r.observed?fmt(r.bips)+' bips':'sem registro'}" aria-pressed="${selectedHour===r.hour}" title="${r.hour}h · ${r.observed?fmt(r.bips)+' bips':'sem registro'}"><b>${r.observed?fmt(r.bips):''}</b><i style="height:${r.observed?Math.max(2,r.bips/max*160):2}px"></i><span>${String(r.hour).padStart(2,'0')}</span></button>`).join('');
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
function miniHours(hours){return '<div class="mini-hours">'+hours.map((n,h)=>n>0?`<span><small>${String(h).padStart(2,'0')}h</small><b>${fmt(n)}</b></span>`:'').join('')+'</div>';}
function paintReasons(rows){$('reason-count').textContent=rows.length+' motivos';$('reason-rows').innerHTML=rows.map(r=>`<tr><td><details class="reason-detail"><summary>${esc(r.name)}</summary><p>${fmt(r.operators)} colaboradores com registro</p>${miniHours(r.hours)}</details></td><td>${fmt(r.bips)}</td><td>${fmt(r.shipments)}</td><td>${pct(r.share)}</td><td>${pct(r.cumulative)}</td></tr>`).join('')||'<tr><td colspan="5">Sem registros neste recorte.</td></tr>';}
function paintPeople(){if(!current||current.view!=='soc')return;const q=norm($('search').value);const rows=current.people.filter(p=>norm(p.name).includes(q));$('people-list').innerHTML=rows.slice(0,peopleLimit).map((p,i)=>`<details class="person"><summary><span class="rank">${String(i+1).padStart(2,'0')}</span><span class="avatar">${esc(p.name.replace(/^\[[^\]]*\]/,'').trim().slice(0,2).toUpperCase())}</span><span class="person-name"><b>${esc(p.name)}</b><small>${p.reasons.length} motivos de tratativa</small></span><span class="person-total"><b>${fmt(p.bips)}</b><small>bips · ${fmt(p.shipments)} pacotes</small></span></summary><div class="person-detail"><h3>PRODUÇÃO POR HORA</h3>${miniHours(p.hours)}<h3>MOTIVOS DA TRATATIVA</h3>${p.reasons.map(r=>`<div class="detail-reason"><span>${esc(r.name)}</span><b>${fmt(r.bips)} bips</b></div>`).join('')}</div></details>`).join('')||'<p class="no-data">Nenhum colaborador neste recorte.</p>';$('more').hidden=rows.length<=peopleLimit;}
function paintSoc(data){
  $('soc-content').hidden=false;$('pick-soc').hidden=true;$('soc-title').textContent=short(data.soc);$('scope').textContent=short(data.soc)+' · somente esta estação';
  const period=selectedHour===null?'Dia completo':String(selectedHour).padStart(2,'0')+'h · Hora selecionada';$('detail-period').textContent=period;$('hour-caption').textContent=period;$('bips-caption').textContent=period;
  $('bips').textContent=fmt(data.bips);$('shipments').textContent=fmt(data.shipments);$('operators').textContent=fmt(data.operators);$('saved-hours').textContent=data.coverage.length+'/24';$('saved-range').textContent=data.coverage.length?'Do dia operacional selecionado':'Aguardando a primeira observação';$('empty').hidden=data.series.some(r=>r.observed);$('clear-hour').hidden=selectedHour===null;
  options($('flow'),data.available_flows,'Todos os fluxos');options($('reason'),data.available_reasons,'Todos os motivos');
  paintHourChart(data.daily_series);paintPareto(data.reasons,data.bips);paintReasons(data.reasons);paintPeople();
  $('flows').innerHTML=data.flows.map(r=>`<div class="reason"><div class="reason-line"><span>${esc(r.name)}</span><b>${fmt(r.bips)} · ${pct(data.bips?r.bips/data.bips:0)}</b></div><div class="track"><i style="width:${data.bips?r.bips/data.bips*100:0}%"></i></div></div>`).join('')||'<p class="no-data">Sem fluxo registrado.</p>';
  $('flow-summary').textContent=`${fmt(data.bips)} bips · ${fmt(data.shipments)} pacotes no recorte`;
  const coverage=new Map(data.coverage.map(r=>[r.hour,r]));$('coverage').innerHTML=Array.from({length:24},(_,h)=>`<span class="${coverage.has(h)?'saved':''}" title="${coverage.has(h)?'Hora preservada. Última observação: '+new Date(coverage.get(h).last_seen).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'}):'Sem observação salva'}">${String(h).padStart(2,'0')}h</span>`).join('');
}
async function load(){
  const requestVersion=++version;if(!$('day').value)return;
  if(view==='soc'&&!$('soc').value){$('scope').textContent='Escolha uma estação';$('sync').textContent='Aguardando seleção do SOC';$('pick-soc').hidden=false;$('soc-content').hidden=true;$('refresh').disabled=false;return;}
  $('refresh').disabled=true;$('error').hidden=true;$('sync').textContent='Atualizando o recorte…';
  if(view==='soc'){$('soc-content').hidden=true;$('pick-soc').hidden=true;}
  const p=new URLSearchParams({view,day:$('day').value});if(view==='soc'){p.set('soc',$('soc').value);p.set('flow',$('flow').value);p.set('reason',$('reason').value);if(selectedHour!==null)p.set('hour',selectedHour);}
  try{const data=await api('/api/dashboard?'+p);if(requestVersion!==version)return;current=data;syncStatus(data.sync);if(view==='overall'){$('scope').textContent='Todos os SOCs · Processado H/H';paintNetwork();}else paintSoc(data);}
  catch(e){if(requestVersion!==version)return;current=null;$('error').textContent=e.message;$('error').hidden=false;$('sync').textContent='Atualização não concluída';if(view==='soc'){$('soc-content').hidden=true;$('pick-soc').hidden=false;}}
  finally{if(requestVersion===version)$('refresh').disabled=false;}
}
async function init(){
  try{catalog=await api('/api/catalog');options($('soc'),catalog.stations,'Escolha um SOC');const p=new URLSearchParams(location.search),station=document.querySelector('[data-station]').dataset.station;
    $('soc').value=catalog.stations.includes(p.get('soc'))?p.get('soc'):catalog.stations.includes(station)?station:'';$('soc').dispatchEvent(new Event('change'));
    $('day').value=/^\d{4}-\d{2}-\d{2}$/.test(p.get('day')||'')?p.get('day'):catalog.days[0]||new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    // Os filtros de motivo e fluxo são sempre derivados apenas da estação escolhida.
    if(p.get('flow'))options($('flow'),[p.get('flow')],'Todos os fluxos');$('flow').value=p.get('flow')||'';
    if(p.get('reason'))options($('reason'),[p.get('reason')],'Todos os motivos');$('reason').value=p.get('reason')||'';
    const h=p.get('hour');selectedHour=h!==null&&/^\d+$/.test(h)&&Number(h)<24?Number(h):null;
    view=p.get('view')==='overall'?'overall':p.get('view')==='soc'?'soc':$('soc').value?'soc':'overall';setView(view,false);
  }catch(e){$('error').textContent=e.message;$('error').hidden=false;}
}
for(const name of ['overall','soc']){$('tab-'+name).addEventListener('click',()=>setView(name));$('tab-'+name).addEventListener('keydown',e=>{if(['ArrowRight','ArrowLeft','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?'overall':e.key==='End'?'soc':name==='overall'?'soc':'overall';setView(next);$('tab-'+next).focus();}});}
for(const id of ['day','soc'])$(id).addEventListener('change',()=>{selectedHour=null;peopleLimit=25;options($('flow'),[],'Todos os fluxos');options($('reason'),[],'Todos os motivos');if(!$('day').value)return;saveLocation();load();});
for(const id of ['flow','reason'])$(id).addEventListener('change',()=>{peopleLimit=25;saveLocation();load();});
$('refresh').addEventListener('click',load);$('network-search').addEventListener('input',paintNetwork);
$('matrix-body').addEventListener('click',e=>{const b=e.target.closest('[data-soc]');if(b){$('soc').value=b.dataset.soc;$('soc').dispatchEvent(new Event('change'));selectedHour=null;setView('soc');}});
$('chart').addEventListener('click',e=>{const b=e.target.closest('[data-hour]');if(b){const h=Number(b.dataset.hour);selectedHour=selectedHour===h?null:h;peopleLimit=25;saveLocation();load();}});
$('clear-hour').addEventListener('click',()=>{selectedHour=null;saveLocation();load();});
$('pareto-key').addEventListener('click',e=>{const b=e.target.closest('[data-reason]');if(b){$('reason').value=b.dataset.reason;saveLocation();load();}});
$('search').addEventListener('input',()=>{peopleLimit=25;paintPeople();});$('more').addEventListener('click',()=>{peopleLimit+=25;paintPeople();});
window.addEventListener('popstate',()=>init());setInterval(()=>{if(!document.hidden)load();},60000);init();
