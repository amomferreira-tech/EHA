"""Contrato da base agregada. Cutoff é mantido como enviado pela fonte."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json

DIMS = ('soc_name', 'operator', 'exception_reason', 'fluxo', 'sub_area', 'before_station_type')
REQUIRED = ('cutoff', 'hora_resolucao', *(k for k in DIMS if k!='sub_area'), 'resolved_shipment', 'resolved_bips')


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
    if headers.count('sub_area')==1:
        positions['sub_area']=headers.index('sub_area')
    grouped = defaultdict(lambda: [0, 0])
    for line, row in enumerate(values[1:], 2):
        if not any(str(v).strip() for v in row):
            continue
        data = {k: row[p] if p < len(row) else '' for k, p in positions.items()}
        try:
            day = day_value(data['cutoff'])
            hour = integer(data['hora_resolucao'])
            if hour > 23 or not str(data['soc_name']).strip():
                raise ValueError('Hora ou estação inválida.')
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
        buckets[key[:3]].append(dict(zip((*DIMS, 'bips', 'shipments'), (*key[2:], *counts))))
    return dict(buckets)


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True,
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
