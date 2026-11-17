'use strict';
function paintPeriod(data){
  const definition=data.period||{kind:'day',days:1,start:data.day,end:data.day};
  const names={day:'Dia',week:'Semana',month:'Mês'};
  const day=value=>String(value).slice(0,10).split('-').reverse().join('/');
  $('period-panel').hidden=definition.kind==='day';
  $('day-label').textContent=definition.kind==='day'?'Dia operacional':'Data de referência';
  $('network-period-note').textContent=definition.kind==='day'?'Bips realizados das 06h D0 às 05h D+1 para todos os SOCs. Clique em uma estação para abrir o detalhe.':'Acumulado de cada faixa horária no período, das 06h D0 às 05h D+1. Clique em uma unidade para abrir o detalhe.';
  $('hourly-title').textContent=definition.kind==='day'?'Bips realizados · H/H':'Bips por faixa horária · acumulado do período';
  if(definition.kind==='day')return;
  const rows=data.daily_totals||[],observed=rows.filter(r=>r.observed),max=Math.max(1,...rows.map(r=>r.bips));
  $('period-title').textContent=names[definition.kind]+' · produção por dia';
  $('period-range').textContent=day(definition.start)+' a '+day(definition.end)+(definition.kind==='week'?' · Segunda a domingo':'');
  $('period-total').textContent=fmt(data.bips)+' bips';
  $('period-observed').textContent=observed.length+'/'+definition.days+' dias com registro';
  const soc=data.view==='soc';
  $('period-head').innerHTML='<tr><th>DIA OPERACIONAL</th><th>BIPS REALIZADOS</th>'+(soc?'<th>PACOTES</th><th>COLABORADORES</th>':'<th>UNIDADES</th>')+'<th>HORAS COM REGISTRO</th></tr>';
  $('period-rows').innerHTML=rows.map(r=>'<tr><td><button class="period-day" data-period-day="'+esc(r.day)+'">'+day(r.day)+' ↗</button></td><td><div class="period-volume"><strong>'+ (r.observed?fmt(r.bips):'—')+'</strong><span><i style="width:'+(r.observed?r.bips/max*100:0)+'%"></i></span></div></td>'+(soc?'<td>'+(r.observed?fmt(r.shipments):'—')+'</td><td>'+(r.observed?fmt(r.operators):'—')+'</td>':'<td>'+(r.observed?fmt(r.stations):'—')+'</td>')+'<td>'+(r.observed?fmt(r.hours):'—')+'</td></tr>').join('');
}
document.getElementById('period-rows')?.addEventListener('click',event=>{
  const button=event.target.closest('[data-period-day]');
  if(!button)return;
  $('period').value='day';$('day').value=button.dataset.periodDay;
  selectedHour=null;selectedShift='';peopleLimit=100;saveLocation();load();
});
