"""Turnos por SOC. A ordem muda; cutoff e horas da fonte são preservados."""
import re


def parse_starts(values):
    if not isinstance(values,(list,tuple)) or len(values)!=3:
        raise ValueError('Informe o início de T1, T2 e T3.')
    result=[]
    for i,value in enumerate(values,1):
        if not isinstance(value,str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):00',value):
            raise ValueError(f'T{i}: use uma hora cheia, como 06:00 ou 07:00. A base é horária.')
        result.append(int(value[:2]))
    validate_starts(result)
    return result


def validate_starts(starts):
    if not isinstance(starts,(list,tuple)) or len(starts)!=3 or any(type(h) is not int or not 0<=h<=23 for h in starts):
        raise ValueError('Horários de turno inválidos.')
    offsets=[(h-starts[0])%24 for h in starts]
    if not 0<offsets[1]<offsets[2]<24:
        raise ValueError('Os turnos devem seguir T1 → T2 → T3, com inícios diferentes, em um ciclo de 24 horas.')


def schedule(starts=None,configured=False,version=0,updated_by=None,updated_at=None):
    starts=starts or [7,15,23]
    validate_starts(starts)
    order=[(starts[0]+i)%24 for i in range(24)]
    shifts=[]
    if configured:
        for i,start in enumerate(starts):
            end=starts[(i+1)%3]
            shifts.append(dict(id=f't{i+1}',name=f'T{i+1}',start=start,end=end,
                               hours=[(start+j)%24 for j in range((end-start)%24)]))
    return dict(configured=configured,starts=list(starts),hour_order=order,shifts=shifts,
                version=version,updated_by=updated_by,updated_at=updated_at)


def shift_totals(rows,soc,definition,flow='',reason=''):
    filtered=[r for r in rows if r['soc_name']==soc and (not flow or r['fluxo']==flow)
              and (not reason or (r['exception_reason'] or 'Não informado')==reason)]
    result=[]
    for item in definition['shifts']:
        selected=[r for r in filtered if r['hour'] in item['hours']]
        result.append(dict(**item,bips=sum(r['bips'] for r in selected),
            shipments=sum(r['shipments'] for r in selected),observed_hours=len({r['hour'] for r in selected})))
    return result
