"""Contrato da base agregada. Cutoff é mantido como enviado pela fonte."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
import calendar


def period_range(day,period='day'):
    anchor=date.fromisoformat(day)
    if period=='day':
        start=end=anchor
    elif period=='week':
        start=anchor-timedelta(days=anchor.weekday())
        end=start+timedelta(days=6)
    elif period=='month':
        start=anchor.replace(day=1)
        end=anchor.replace(day=calendar.monthrange(anchor.year,anchor.month)[1])
    else:
        raise ValueError('Período inválido.')
    return dict(kind=period,start=start.isoformat(),end=end.isoformat(),days=(end-start).days+1)


def daily_summary(rows,start,end,soc='',flow='',reason='',hour=None):
    entries={}
    current=date.fromisoformat(start)
    last=date.fromisoformat(end)
    while current<=last:
        key=current.isoformat()
        entries[key]=dict(day=key,bips=0,shipments=0,observed=False,people=set(),stations=set(),hours=set())
        current+=timedelta(days=1)
    for r in rows:
        if ((soc and r['soc_name']!=soc) or (flow and r.get('fluxo')!=flow)
            or (reason and (r.get('exception_reason') or 'Não informado')!=reason)
            or (hour is not None and r['hour']!=hour)):
            continue
        key=str(r.get('operational_day') or r.get('day') or start)[:10]
        if key not in entries:
            continue
        item=entries[key]
        item['observed']=True
        item['bips']+=r['bips']
        item['shipments']+=r.get('shipments',0)
        item['stations'].add(r['soc_name'])
        item['hours'].add((r['soc_name'],r['hour']))
        if r.get('operator'):
            item['people'].add((r['soc_name'],r['operator']))
    return [dict(day=r['day'],bips=r['bips'],shipments=r['shipments'],observed=r['observed'],
        operators=len(r['people']),stations=len(r['stations']),hours=len(r['hours'])) for r in entries.values()]


def add_period_breakdown(result,rows,period,soc='',flow='',reason='',hour=None):
    """Colunas de dias/semanas com os mesmos filtros do consolidado."""
    if period['kind']=='day':
        return
    columns=[]
    positions={}
    current=date.fromisoformat(period['start'])
    end=date.fromisoformat(period['end'])
    while current<=end:
        key=(current-timedelta(days=current.weekday())).isoformat() if period['kind']=='month' else current.isoformat()
        if key not in positions:
            positions[key]=len(columns)
            columns.append(dict(key=key,label=f'S{current.isocalendar().week:02d}' if period['kind']=='month' else current.strftime('%d/%m'),
                start=current.isoformat(),end=current.isoformat(),observed=False,bips=0))
        columns[positions[key]]['end']=current.isoformat()
        current+=timedelta(days=1)
    n=len(columns)
    matrix={r['soc']:r for r in result.get('matrix',[])}
    people={(r['soc'],r['name']):r for r in result.get('people',[])}
    reasons={r['name']:r for r in result.get('reasons',[])}
    operator_reasons={}
    for item in matrix.values():
        item['period_values']=[None]*n
    for key,item in people.items():
        item['period_values']=[0]*n
        item['period_shipments']=[0]*n
        for detail in item['reasons']:
            detail['period_values']=[0]*n
            operator_reasons[(*key,detail['name'])]=detail
    for item in reasons.values():
        item['period_values']=[0]*n
    for row in rows:
        if ((soc and row['soc_name']!=soc) or (flow and row.get('fluxo')!=flow)
            or (reason and (row.get('exception_reason') or 'Não informado')!=reason)
            or (hour is not None and row['hour']!=hour)):
            continue
        day=date.fromisoformat(str(row.get('operational_day') or row.get('day') or period['start'])[:10])
        key=(day-timedelta(days=day.weekday())).isoformat() if period['kind']=='month' else day.isoformat()
        if key not in positions:
            continue
        i=positions[key]
        columns[i]['observed']=True
        columns[i]['bips']+=row['bips']
        station=matrix.get(row['soc_name'])
        if station is not None:
            station['period_values'][i]=(station['period_values'][i] or 0)+row['bips']
        name=row.get('operator') or 'Não informado'
        op=people.get((row['soc_name'],name))
        if op is not None:
            op['period_values'][i]+=row['bips']
            op['period_shipments'][i]+=row.get('shipments',0)
        reason_name=row.get('exception_reason') or 'Não informado'
        detail=operator_reasons.get((row['soc_name'],name,reason_name))
        if detail is not None:
            detail['period_values'][i]+=row['bips']
        detail=reasons.get(reason_name)
        if detail is not None:
            detail['period_values'][i]+=row['bips']
    result['period_columns']=columns

DIMS = ('soc_name', 'operator', 'exception_reason', 'fluxo', 'sub_area', 'before_station_type')
REQUIRED = ('cutoff', 'hora_resolucao', *(k for k in DIMS if k not in ('sub_area','before_station_type')), 'resolved_shipment', 'resolved_bips')


def integer(value):
    try:
        n = Decimal(str(value).strip())
        if not n.is_finite() or n < 0 or n != n.to_integral_value():
            raise ValueError('Contagem deve ser inteira e não negativa.')
        return int(n)
    except (InvalidOperation, TypeError):
        raise ValueError('Contagem inválida.') from None


def day_value(value):
    if isinstance(value, (int, float)):
        if value != int(value):
            raise ValueError('Cutoff contém horário inesperado.')
        return (date(1899, 12, 30) + timedelta(days=int(value))).isoformat()
    s = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError('Cutoff inválido.')


def normalize(values):
    if len(values) < 2:
        raise ValueError('Fonte vazia. Histórico preservado.')
    headers = [str(v).strip().lower() for v in values[0]]
    if any(headers.count(k) != 1 for k in REQUIRED):
        raise ValueError('Cabeçalhos ausentes ou duplicados na fonte.')
    positions = {k: headers.index(k) for k in REQUIRED}
    for optional in ('sub_area','before_station_type','soc_code'):
        if headers.count(optional)>1:
            raise ValueError('Cabeçalho opcional duplicado na fonte.')
        if optional in headers:
            positions[optional]=headers.index(optional)
    grouped = defaultdict(lambda: [0, 0])
    station_codes={}
    for line, row in enumerate(values[1:], 2):
        if not any(str(v).strip() for v in row):
            continue
        data = {k: row[p] if p < len(row) else '' for k, p in positions.items()}
        try:
            day = day_value(data['cutoff'])
            hour = integer(data['hora_resolucao'])
            if hour > 23 or not str(data['soc_name']).strip():
                raise ValueError('Hora ou estação inválida.')
            code=str(data.get('soc_code','')).strip()
            station=str(data['soc_name']).strip()
            if code:
                if len(code)>80 or (station in station_codes and station_codes[station]!=code):
                    raise ValueError('Código de unidade inválido ou divergente na carga.')
                station_codes[station]=code
            dims = tuple(str(data.get(k,'')).strip() for k in DIMS)
            key = (day, hour, *dims)
            grouped[key][0] += integer(data['resolved_bips'])
            grouped[key][1] += integer(data['resolved_shipment'])
        except (ValueError, OverflowError) as exc:
            raise ValueError(f'Linha {line}: {exc}') from None
    if not grouped:
        raise ValueError('Nenhuma linha válida. Histórico preservado.')
    buckets = defaultdict(list)
    for key, counts in sorted(grouped.items()):
        record=dict(zip((*DIMS, 'bips', 'shipments'), (*key[2:], *counts)))
        if station_codes.get(key[2]):
            record['soc_code']=station_codes[key[2]]
        buckets[key[:3]].append(record)
    return dict(buckets)


def fingerprint(rows):
    # O código é um rótulo da unidade; alterar o rótulo não altera a produção.
    facts=[{k:v for k,v in row.items() if k!='soc_code'} for row in rows]
    return hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def summarize(rows, stations, day, soc='', flow='', hour=None, reason=''):
    filtered = [r for r in rows if (not soc or r['soc_name'] == soc)
                and (not flow or r['fluxo'] == flow)
                and (not reason or (r['exception_reason'] or 'Não informado') == reason)]
    if hour is not None:
        filtered = [r for r in filtered if r['hour'] == hour]
    series = [dict(hour=h, bips=0, shipments=0, observed=False) for h in range(24)]
    matrix = {s: dict(soc=s, bips=0, shipments=0, hours=[None]*24) for s in ([soc] if soc else stations)}
    operators, reasons, flows = {}, {}, defaultdict(int)
    for r in filtered:
        h, b, p = r['hour'], r['bips'], r['shipments']
        for k, v in [('bips', b), ('shipments', p)]:
            series[h][k] += v
            matrix[r['soc_name']][k] += v
        series[h]['observed'] = True
        matrix[r['soc_name']]['hours'][h] = (matrix[r['soc_name']]['hours'][h] or 0) + b
        opkey = (r['soc_name'], r['operator'])
        op = operators.setdefault(opkey, dict(name=r['operator'] or 'Não informado',
                    soc=r['soc_name'], bips=0, shipments=0, reasons={}, hours=[0]*24,shipment_hours=[0]*24))
        op['bips'] += b
        op['shipments'] += p
        op['hours'][h] += b
        op['shipment_hours'][h] += p
        op_reason=op['reasons'].setdefault(r['exception_reason'] or 'Não informado',
            dict(bips=0,shipments=0,hours=[0]*24))
        op_reason['bips']+=b
        op_reason['shipments']+=p
        op_reason['hours'][h]+=b
        reason_name=r['exception_reason'] or 'Não informado'
        entry=reasons.setdefault(reason_name,dict(name=reason_name,bips=0,shipments=0,hours=[0]*24,operators=set()))
        entry['bips']+=b
        entry['shipments']+=p
        entry['hours'][h]+=b
        if r['operator']:
            entry['operators'].add((r['soc_name'],r['operator']))
        flows[r['fluxo'] or 'Não informado']+=b
    ops = sorted(operators.values(), key=lambda r: (-r['bips'], r['name']))
    for op in ops:
        op['reasons'] = sorted([dict(name=k, **v) for k, v in op['reasons'].items()], key=lambda r: -r['bips'])
    observed = [r for r in series if r['observed']]
    peak = max(observed, key=lambda r: r['bips']) if observed else None
    bips=sum(r['bips'] for r in filtered)
    pareto=sorted(reasons.values(),key=lambda r:(-r['bips'],r['name']))
    accumulated=0
    for r in pareto:
        accumulated+=r['bips']
        r['operators']=len(r['operators'])
        r['share']=r['bips']/bips if bips else 0
        r['cumulative']=accumulated/bips if bips else 0
    return dict(day=day, bips=bips, shipments=sum(r['shipments'] for r in filtered),
                operators=len(ops), active_socs=len({r['soc_name'] for r in filtered}), peak=peak,
                series=series, matrix=sorted(matrix.values(), key=lambda r: (-r['bips'], r['soc'])),
                people=ops, reasons=pareto,flows=sorted([dict(name=k,bips=v) for k,v in flows.items()],key=lambda r:-r['bips']))


def overall(rows,stations,day):
    """Consolidado H/H sem dados de colaboradores e motivos."""
    matrix={s:dict(soc=s,bips=0,hours=[None]*24) for s in stations}
    series=[dict(hour=h,bips=0,observed=False) for h in range(24)]
    for r in rows:
        h,b=r['hour'],r['bips']
        item=matrix.setdefault(r['soc_name'],dict(soc=r['soc_name'],bips=0,hours=[None]*24))
        item['bips']+=b
        item['hours'][h]=(item['hours'][h] or 0)+b
        series[h]['bips']+=b
        series[h]['observed']=True
    return dict(day=day,bips=sum(r['bips'] for r in rows),series=series,
        matrix=sorted(matrix.values(),key=lambda r:(-r['bips'],r['soc'])),active_socs=len({r['soc_name'] for r in rows}))
