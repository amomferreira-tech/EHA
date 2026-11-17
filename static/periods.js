'use strict';
const periodDate=value=>String(value).slice(0,10).split('-').reverse().join('/');
function periodColumnLabel(column,data){
  if(data.period.kind==='month')return column.label;
  return new Intl.DateTimeFormat('pt-BR',{weekday:'short',timeZone:'UTC'}).format(new Date(column.start+'T12:00:00Z'));
}
function periodColumnSmall(column,data){return data.period.kind==='month'?periodDate(column.start).slice(0,5)+'–'+periodDate(column.end).slice(0,5):column.label;}
function renderPeriodChart(container,data){
  const columns=data.period_columns||[],max=Math.max(1,...columns.map(c=>c.bips));
  container.classList.add('aggregate-chart');
  container.style.gridTemplateColumns='repeat('+Math.max(1,columns.length)+',minmax(70px,1fr))';
  container.innerHTML=columns.map(column=>{
    const height=column.observed?Math.max(2,column.bips/max*160):2;
    const label=periodColumnLabel(column,data),small=periodColumnSmall(column,data);
    const detail=periodDate(column.start)+(column.end!==column.start?' a '+periodDate(column.end):'');
    return '<button class="hour-bar period-bar '+(column.observed?'':'missing')+'" data-period-anchor="'+esc(column.start)+'" data-next-period="'+(data.period.kind==='month'?'week':'day')+'" aria-label="'+esc(label+' · '+detail+' · '+(column.observed?fmt(column.bips)+' bips':'sem registro'))+'" title="'+esc(detail)+'"><b class="'+(height>=26?'in-bar':'above-bar')+'" style="bottom:'+(40+height+(height>=26?-20:5))+'px">'+(column.observed?fmt(column.bips):'')+'</b><i style="height:'+height+'px"></i><span>'+esc(label)+'<small class="day-marker">'+esc(small)+'</small></span></button>';
  }).join('');
}
function paintProductionChart(data){
  const hourly=(data.period?.kind||'day')==='day';
  $('hourly-title').textContent=hourly?'Bips realizados · H/H':data.period.kind==='week'?'Bips realizados · por dia':'Bips realizados · por semana';
  $('production-chart-note').textContent=hourly?'Selecione uma barra para detalhar os motivos e colaboradores daquela hora.':'Selecione '+(data.period.kind==='week'?'um dia para abrir o H/H.':'uma semana para abrir os dias. As semanas nas bordas consideram somente os dias do mês selecionado.');
  $('people-description').textContent=hourly?'Bips realizados por hora. Expanda o operador para abrir seus motivos de tratativa.':'Bips realizados por '+(data.period.kind==='week'?'dia da semana':'semana do mês')+'. Expanda o operador para abrir seus motivos de tratativa.';
  if(hourly){$('chart').classList.remove('aggregate-chart');$('chart').style.gridTemplateColumns='';paintHourChart(data.daily_series);}
  else renderPeriodChart($('chart'),data);
}
function miniPeriodValues(values){
  return '<div class="mini-hours">'+(current.period_columns||[]).map((column,i)=>values?.[i]>0?'<span><small>'+esc(column.label)+'</small><b>'+fmt(values[i])+'</b></span>':'').join('')+'</div>';
}
function paintPeriod(data){
  const definition=data.period||{kind:'day',days:1,start:data.day,end:data.day};
  $('period-panel').hidden=definition.kind==='day'||data.view==='soc';
  $('day-label').textContent=definition.kind==='day'?'Dia operacional':'Data de referência';
  $('production-title').textContent=definition.kind==='day'?'Produção por hora':definition.kind==='week'?'Produção por dia':'Produção por semana';
  $('network-title').textContent=definition.kind==='day'?'Processado hora a hora':definition.kind==='week'?'Processado por dia':'Processado por semana';
  $('network-period-note').textContent=definition.kind==='day'?'Bips realizados das 06h D0 às 05h D+1 para todos os SOCs. Clique em uma unidade para abrir o detalhe.':definition.kind==='week'?'Produção por dia da semana em cada unidade.':'Produção por semana do mês em cada unidade. As semanas nas bordas incluem somente os dias do mês.';
  if(definition.kind==='day')return;
  $('period-title').textContent=definition.kind==='week'?'Bips realizados · por dia':'Bips realizados · por semana';
  $('period-range').textContent=periodDate(definition.start)+' a '+periodDate(definition.end)+(definition.kind==='week'?' · Segunda a domingo':' · Semanas do mês');
  $('period-total').textContent=fmt(data.bips)+' bips';
  $('period-observed').textContent=(data.daily_totals||[]).filter(r=>r.observed).length+'/'+definition.days+' dias com registro';
  if(data.view==='overall')renderPeriodChart($('period-chart'),data);
}
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-period-anchor]');
  if(!button)return;
  $('period').value=button.dataset.nextPeriod;$('day').value=button.dataset.periodAnchor;
  selectedHour=null;selectedShift='';peopleLimit=100;saveLocation();load();
});

function periodHeadCell(column,data){return '<button class="operator-hour" data-period-anchor="'+esc(column.start)+'" data-next-period="'+(data.period.kind==='month'?'week':'day')+'" title="'+esc(periodDate(column.start)+' a '+periodDate(column.end))+'">'+esc(periodColumnLabel(column,data))+'<small>'+esc(periodColumnSmall(column,data))+'</small><small>'+(column.observed?'SALVO':'SEM REGISTRO')+'</small></button>';}
function paintPeriodPeople(){
  if(operatorStation!==current.soc){expandedOperators.clear();operatorStation=current.soc;}
  const columns=current.period_columns||[],q=norm($('search').value),rows=current.people.filter(p=>norm(p.name).includes(q));
  const cell=(values,i)=>columns[i].observed?fmt(values?.[i]||0):'—';
  $('people-head').innerHTML='<tr><th scope="col">COLABORADOR</th><th scope="col">TOTAL BIPS</th>'+columns.map(c=>'<th scope="col">'+periodHeadCell(c,current)+'</th>').join('')+'</tr>';
  const totals=columns.map((_,i)=>rows.reduce((sum,p)=>sum+(p.period_values?.[i]||0),0));
  const bips=rows.reduce((sum,p)=>sum+p.bips,0),shipments=rows.reduce((sum,p)=>sum+p.shipments,0);
  $('people-total').textContent=fmt(bips)+' bips · '+fmt(shipments)+' pacotes';
  const overall='<tr class="operator-overall"><td>'+(q?'TOTAL DO FILTRO':'TOTAL DO SOC')+'</td><td>'+fmt(bips)+'</td>'+columns.map((_,i)=>'<td>'+cell(totals,i)+'</td>').join('')+'</tr>';
  $('people-list').innerHTML=overall+rows.slice(0,peopleLimit).map(p=>{
    const expanded=expandedOperators.has(p.name);
    return '<tr class="operator-row"><td><button class="operator-toggle" data-operator="'+esc(p.name)+'" aria-expanded="'+expanded+'"><span class="expand-symbol">'+(expanded?'−':'+')+'</span><span>'+esc(p.name)+'</span></button></td><td class="operator-total"><strong>'+fmt(p.bips)+'</strong><small>'+fmt(p.shipments)+' pacotes</small></td>'+columns.map((_,i)=>'<td title="'+fmt(p.period_shipments?.[i]||0)+' pacotes">'+cell(p.period_values,i)+'</td>').join('')+'</tr>'+(expanded?p.reasons.map(r=>'<tr class="operator-reason"><td>↳ '+esc(r.name)+'</td><td><strong>'+fmt(r.bips)+'</strong><small>'+fmt(r.shipments)+' pacotes</small></td>'+columns.map((_,i)=>'<td>'+cell(r.period_values,i)+'</td>').join('')+'</tr>').join(''):'');
  }).join('')+(rows.length?'':'<tr><td colspan="'+(columns.length+2)+'" class="no-data">Nenhum colaborador neste recorte.</td></tr>');
  $('more').hidden=rows.length<=peopleLimit;
}
function paintPeriodNetwork(){
  const columns=current.period_columns||[],q=norm($('network-search').value),rows=current.matrix.filter(r=>norm(r.soc+' '+short(r.soc)).includes(q));
  $('overall-bips').textContent=fmt(current.bips);$('soc-count').textContent=fmt(current.active_socs);$('network-hours').textContent=(current.daily_totals||[]).filter(r=>r.observed).length+'/'+current.period.days+' dias com registro';
  $('matrix-head').innerHTML='<tr><th>UNIDADE</th><th>TOTAL BIPS</th>'+columns.map(c=>'<th>'+periodHeadCell(c,current)+'</th>').join('')+'</tr>';
  const max=Math.max(1,...rows.flatMap(r=>(r.period_values||[]).filter(v=>v!==null)));
  $('matrix-body').innerHTML=rows.map(r=>'<tr><td><button class="soc-link" data-soc="'+esc(r.soc)+'">'+esc(short(r.soc))+'<span>'+esc(stationCode(r.soc)?stationName(r.soc):'Ver detalhe ↗')+'</span></button></td><td>'+((r.period_values||[]).some(v=>v!==null)?fmt(r.bips):'—')+'</td>'+columns.map((_,i)=>{const value=r.period_values?.[i];return '<td'+(value==null?'':' style="background:rgba(238,77,45,'+(.025+.2*value/max)+')"')+'>'+(value==null?'—':fmt(value))+'</td>';}).join('')+'</tr>').join('');
  $('matrix-foot').innerHTML=rows.length?'<tr><td>'+(q?'TOTAL DO FILTRO':'TOTAL GERAL')+'</td><td>'+fmt(rows.reduce((s,r)=>s+r.bips,0))+'</td>'+columns.map((_,i)=>{const values=rows.map(r=>r.period_values?.[i]).filter(v=>v!=null);return '<td>'+(values.length?fmt(values.reduce((a,b)=>a+b,0)):'—')+'</td>';}).join('')+'</tr>':'';
  $('network-empty').hidden=rows.length>0;$('network-empty').textContent='Nenhuma unidade encontrada.';
}
