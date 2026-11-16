"""Serviço Railway separado, sem servidor HTTP. Uma transação por carga válida."""
import logging
import os
import time
from domain import normalize
from source import load_sheet
from store import connection, migrate, save_buckets

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def collect():
    # Session lock cobre leitura e gravação; duas réplicas não coletam simultaneamente.
    with connection() as lock:
        if not lock.execute('SELECT pg_try_advisory_lock(8520982) AS acquired').fetchone()['acquired']:
            return
        lock.commit()
        run_id = None
        try:
            with connection() as conn:
                run_id = conn.execute("INSERT INTO eha_runs(status) VALUES('running') RETURNING id").fetchone()['id']
            buckets = normalize(load_sheet())
            with connection() as conn:
                changed = save_buckets(conn, run_id, buckets)
                conn.execute("UPDATE eha_runs SET status='ok',completed_at=now(),bucket_count=%s WHERE id=%s", (len(buckets),run_id))
            logging.info('Coleta concluída: %s horas observadas, %s revisões.', len(buckets), changed)
        except Exception as exc:
            # Não persiste URL, chave, token nem conteúdo de linhas em logs.
            logging.error('Coleta recusada: %s', type(exc).__name__)
            if run_id:
                with connection() as conn:
                    conn.execute("UPDATE eha_runs SET status='error',completed_at=now(),error=%s WHERE id=%s",
                                 (type(exc).__name__,run_id))
        finally:
            lock.execute('SELECT pg_advisory_unlock(8520982)')
            lock.commit()


if __name__ == '__main__':
    migrate()
    while True:
        try:
            collect()
        except Exception as exc:
            logging.error('Banco indisponível: %s', type(exc).__name__)
        time.sleep(max(60, int(os.getenv('SYNC_SECONDS','300'))))
