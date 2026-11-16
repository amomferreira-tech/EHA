"""Serviço Railway separado, sem servidor HTTP. Uma transação por carga válida."""
import logging
import os
import time
from domain import normalize
from source import load_sheet
from store import connection, migrate, save_buckets

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def failure_message(exc):
    from requests.exceptions import HTTPError
    from google.auth.exceptions import RefreshError
    import json
    if isinstance(exc,KeyError):
        return 'Configuração incompleta da conta de serviço ou do banco.'
    if isinstance(exc,json.JSONDecodeError):
        return 'GOOGLE_SERVICE_ACCOUNT_JSON não contém um JSON válido.'
    if isinstance(exc,RefreshError):
        return 'Google recusou a credencial da conta de serviço. Confira a chave cadastrada.'
    if isinstance(exc,HTTPError):
        status=exc.response.status_code if exc.response is not None else None
        if status==403:
            return 'Google Sheets negou acesso. Confira a API habilitada e o compartilhamento com a conta de serviço.'
        if status==404:
            return 'Planilha ou aba não encontrada. Confira SPREADSHEET_ID e SHEET_NAME.'
        return f'Falha na leitura do Google Sheets (HTTP {status}).'
    if isinstance(exc,ValueError):
        # normalize() produz mensagens sem nomes nem conteúdo das linhas.
        return 'Fonte ou credencial inválida. Confira cabeçalhos, datas e contagens da aba DB Resolved.'
    return f'Coleta não concluída ({type(exc).__name__}).'


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
            message=failure_message(exc)
            logging.error('Coleta recusada: %s', message)
            if run_id:
                with connection() as conn:
                    conn.execute("UPDATE eha_runs SET status='error',completed_at=now(),error=%s WHERE id=%s",
                                 (message,run_id))
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
