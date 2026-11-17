from pathlib import Path
import os
import psycopg
from psycopg.rows import dict_row
from domain import DIMS, fingerprint
from psycopg.types.json import Jsonb
from schedules import schedule,validate_starts,default_schedule,SOURCE_DAY_START


def connection():
    return psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row,
                          connect_timeout=10, options='-c statement_timeout=60000')


def migrate():
    with connection() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(8520981)')
        conn.execute(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))


def save_buckets(conn, run_id, buckets):
    changed = 0
    codes={soc:r['soc_code'] for (_,_,soc),rows in buckets.items() for r in rows if r.get('soc_code')}
    for soc,code in sorted(codes.items()):
        conn.execute('''INSERT INTO eha_stations(soc_name,soc_code) VALUES(%s,%s)
            ON CONFLICT(soc_name) DO UPDATE SET soc_code=EXCLUDED.soc_code,updated_at=now()
            WHERE eha_stations.soc_code IS DISTINCT FROM EXCLUDED.soc_code''',(soc,code))
    for (day, hour, soc), rows in sorted(buckets.items()):
        digest = fingerprint(rows)
        previous = conn.execute('''SELECT r.fingerprint FROM eha_latest l
            JOIN eha_revisions r ON r.id=l.revision_id WHERE l.day=%s AND l.hour=%s AND l.soc_name=%s''', (day,hour,soc)).fetchone()
        if previous and previous['fingerprint'] == digest:
            conn.execute('UPDATE eha_latest SET last_seen_at=now() WHERE day=%s AND hour=%s AND soc_name=%s', (day,hour,soc))
            continue
        rev = conn.execute('''INSERT INTO eha_revisions(run_id,day,hour,soc_name,fingerprint)
             VALUES(%s,%s,%s,%s,%s) RETURNING id''', (run_id,day,hour,soc,digest)).fetchone()['id']
        with conn.cursor() as cur:
            cur.executemany('''INSERT INTO eha_facts(revision_id,soc_name,operator,exception_reason,
                fluxo,sub_area,before_station_type,bips,shipments) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                [(rev, *(r[k] for k in (*DIMS, 'bips', 'shipments'))) for r in rows])
        conn.execute('''INSERT INTO eha_latest(day,hour,soc_name,revision_id) VALUES(%s,%s,%s,%s)
            ON CONFLICT(day,hour,soc_name) DO UPDATE SET revision_id=EXCLUDED.revision_id,last_seen_at=now()''', (day,hour,soc,rev))
        changed += 1
    return changed


def catalog():
    with connection() as conn:
        stations = [r['soc_name'] for r in conn.execute('''SELECT DISTINCT f.soc_name FROM eha_latest l
            JOIN eha_facts f ON f.revision_id=l.revision_id ORDER BY 1''')]
        days = [r['day'].isoformat() for r in conn.execute(f'''SELECT day FROM eha_latest UNION
            SELECT {_unit_day_sql()} AS day FROM eha_latest l
            LEFT JOIN eha_unit_settings u ON u.soc_name=l.soc_name ORDER BY 1 DESC''')]
        flows = [r['fluxo'] for r in conn.execute('''SELECT DISTINCT f.fluxo FROM eha_latest l
            JOIN eha_facts f ON f.revision_id=l.revision_id WHERE f.fluxo<>'' ORDER BY 1''')]
        station_codes={r['soc_name']:r['soc_code'] for r in conn.execute('SELECT soc_name,soc_code FROM eha_stations')}
    stations.sort(key=lambda name:(station_codes.get(name,name).casefold(),name))
    return dict(stations=stations,days=days,flows=flows,station_codes=station_codes)


def read_day(day,soc):
    with connection() as conn:
        return conn.execute(f'''SELECT l.hour,f.* FROM eha_latest l JOIN eha_facts f
            ON f.revision_id=l.revision_id LEFT JOIN eha_unit_settings u ON u.soc_name=l.soc_name
            WHERE l.day BETWEEN %s::date-1 AND %s::date+1 AND l.soc_name=%s
            AND {_unit_day_sql()}=%s::date ORDER BY l.hour''', (day,day,soc,day)).fetchall()


def _unit_day_sql():
    # A fonte já atribui 00h–05h ao cutoff anterior. Reconstruir o dia civil
    # antes de aplicar T1 evita deslocar a madrugada duas vezes.
    start="COALESCE((u.shift_starts->>0)::integer,CASE WHEN lower(l.soc_name)='soc_rj_jacarepagua' THEN 7 ELSE 6 END)"
    return f'(l.day + (l.hour<{SOURCE_DAY_START})::integer - (l.hour<{start})::integer)'


def read_overall(day):
    with connection() as conn:
        return conn.execute('''SELECT l.soc_name,l.hour,sum(f.bips)::bigint AS bips FROM eha_latest l
            JOIN eha_facts f ON f.revision_id=l.revision_id WHERE l.day=%s
            GROUP BY l.soc_name,l.hour ORDER BY l.soc_name,l.hour''',(day,)).fetchall()


def coverage(day,soc=''):
    with connection() as conn:
        if soc:
            rows=conn.execute(f'''SELECT l.hour,max(l.last_seen_at) AS last_seen,count(*) AS stations
                FROM eha_latest l LEFT JOIN eha_unit_settings u ON u.soc_name=l.soc_name
                WHERE l.day BETWEEN %s::date-1 AND %s::date+1 AND l.soc_name=%s
                AND {_unit_day_sql()}=%s::date GROUP BY l.hour ORDER BY l.hour''',(day,day,soc,day)).fetchall()
        else:
            rows=conn.execute('''SELECT hour,max(last_seen_at) AS last_seen,count(*) AS stations
                FROM eha_latest WHERE day=%s GROUP BY hour ORDER BY hour''',(day,)).fetchall()
    return [dict(hour=r['hour'],last_seen=r['last_seen'].isoformat(),stations=r['stations']) for r in rows]


def sync_status():
    with connection() as conn:
        last = conn.execute('SELECT status,completed_at,error FROM eha_runs ORDER BY id DESC LIMIT 1').fetchone()
        good = conn.execute("SELECT completed_at FROM eha_runs WHERE status='ok' ORDER BY id DESC LIMIT 1").fetchone()
    return dict(last=last, last_success=good['completed_at'] if good else None)


def preference(email, station=None):
    with connection() as conn:
        if station is not None:
            conn.execute('''INSERT INTO eha_preferences(email,station) VALUES(%s,%s)
                ON CONFLICT(email) DO UPDATE SET station=EXCLUDED.station,updated_at=now()''', (email,station))
            return station
        row = conn.execute('SELECT station FROM eha_preferences WHERE email=%s', (email,)).fetchone()
        return row['station'] if row else None


def unit_schedule(soc):
    with connection() as conn:
        row=conn.execute('SELECT * FROM eha_unit_settings WHERE soc_name=%s',(soc,)).fetchone()
    if not row:
        return default_schedule(soc)
    return schedule(row['shift_starts'],True,row['version'],row['updated_by'],row['updated_at'].isoformat())


def save_unit_schedule(soc,starts,actor,expected_version):
    validate_starts(starts)
    with connection() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(8520983,hashtext(%s))',(soc,))
        previous=conn.execute('SELECT version FROM eha_unit_settings WHERE soc_name=%s',(soc,)).fetchone()
        version=previous['version'] if previous else 0
        if version!=expected_version:
            raise ValueError('Esta unidade foi atualizada por outra pessoa. Reabra as configurações antes de salvar.')
        version+=1
        conn.execute('''INSERT INTO eha_unit_settings(soc_name,shift_starts,version,updated_by)
            VALUES(%s,%s,%s,%s) ON CONFLICT(soc_name) DO UPDATE SET shift_starts=EXCLUDED.shift_starts,
            version=EXCLUDED.version,updated_by=EXCLUDED.updated_by,updated_at=now()''',
            (soc,Jsonb(starts),version,actor))
        conn.execute('''INSERT INTO eha_unit_settings_audit(soc_name,shift_starts,version,updated_by)
            VALUES(%s,%s,%s,%s)''',(soc,Jsonb(starts),version,actor))
