'use strict';
const picker=document.getElementById('settings-soc');
picker?.addEventListener('change',()=>{if(picker.value)picker.form.submit();});
const inputs=Array.from(document.querySelectorAll('input[name="shift_start"]'));
function showSchedule(){
  if(!inputs.length)return;
  const starts=inputs.map(input=>/^([01]\d|2[0-3]):00$/.test(input.value)?Number(input.value.slice(0,2)):null);
  const valid=starts.every(h=>h!==null)&&0<(starts[1]-starts[0]+24)%24&&(starts[1]-starts[0]+24)%24<(starts[2]-starts[0]+24)%24;
  inputs.forEach((input,i)=>{
    const end=starts[(i+1)%3],start=starts[i];
    document.getElementById('end-'+i).textContent=end===null?'—':String(end).padStart(2,'0')+':00';
    document.getElementById('duration-'+i).textContent=valid?((end-start+24)%24)+'h':'—';
  });
  const range=document.getElementById('schedule-range'),hours=document.getElementById('schedule-hours');hours.replaceChildren();
  if(!valid){range.textContent='Preencha T1, T2 e T3 em sequência, com inícios diferentes.';return;}
  const first=starts[0],last=(first+23)%24;range.textContent=String(first).padStart(2,'0')+'h D0 → '+String(last).padStart(2,'0')+'h '+(first===0?'D0':'D+1')+' · T1 ao fim do T3';
  for(let offset=0;offset<24;offset++){
    const h=(first+offset)%24,t=offset<(starts[1]-first+24)%24?1:offset<(starts[2]-first+24)%24?2:3;
    const item=document.createElement('span');item.className='preview-t'+t;item.textContent=String(h).padStart(2,'0')+'h '+(h<first?'D+1':'D0');item.title='T'+t;hours.append(item);
  }
}
inputs.forEach(input=>input.addEventListener('input',showSchedule));showSchedule();
for(const time of document.querySelectorAll('time[datetime]')){const date=new Date(time.dateTime);if(!Number.isNaN(date.valueOf()))time.textContent=date.toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',dateStyle:'short',timeStyle:'short'});}
