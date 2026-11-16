from pathlib import Path
import os
import psycopg
from psycopg.rows import dict_row
from domain import DIMS, fingerprint


def connection():
    return psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row,
                          connect_timeout=10, options='-c statement_timeout=60000')


def migrate():
    with connection() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(8520981)')
        conn.execute(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))


def save_buckets(conn, run_id, buckets):
    changed = 0
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
        days = [r['day'].isoformat() for r in conn.execute('SELECT DISTINCT day FROM eha_latest ORDER BY 1 DESC')]
        flows = [r['fluxo'] for r in conn.execute('''SELECT DISTINCT f.fluxo FROM eha_latest l
            JOIN eha_facts f ON f.revision_id=l.revision_id WHERE f.fluxo<>'' ORDER BY 1''')]
    return dict(stations=stations,days=days,flows=flows)


def read_day(day,soc):
    with connection() as conn:
        return conn.execute('''SELECT l.hour,f.* FROM eha_latest l JOIN eha_facts f
            ON f.revision_id=l.revision_id WHERE l.day=%s AND l.soc_name=%s ORDER BY l.hour''', (day,soc)).fetchall()


def read_overall(day):
    with connection() as conn:
        return conn.execute('''SELECT l.soc_name,l.hour,sum(f.bips)::bigint AS bips FROM eha_latest l
            JOIN eha_facts f ON f.revision_id=l.revision_id WHERE l.day=%s
            GROUP BY l.soc_name,l.hour ORDER BY l.soc_name,l.hour''',(day,)).fetchall()


def coverage(day,soc=''):
    with connection() as conn:
        rows=conn.execute('''SELECT hour,max(last_seen_at) AS last_seen,count(*) AS stations
            FROM eha_latest WHERE day=%s AND (%s='' OR soc_name=%s)
            GROUP BY hour ORDER BY hour''',(day,soc,soc)).fetchall()
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
