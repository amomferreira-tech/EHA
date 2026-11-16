import os
import logging
import signal
import subprocess
import sys
import threading

from store import migrate

def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    migrate()
    stopping=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):
        signal.signal(sig,lambda *_: stopping.set())
    children=[]
    try:
        web=subprocess.Popen(["gunicorn", "app:app", "--bind", f"0.0.0.0:{os.getenv('PORT', '8080')}",
            "--workers", "2", "--threads", "4", "--timeout", "60", "--graceful-timeout", "15",
            "--access-logfile", "-", "--access-logformat", "%(h)s %(m)s %(U)s %(s)s"])
        children.append(('web',web))
        if os.getenv('RUN_COLLECTOR','true').strip().lower() not in ('false','0','no'):
            children.append(('coletor',subprocess.Popen([sys.executable,'-u','worker.py'])))
            logging.info('Coletor EHA iniciado junto ao serviço Web.')
        while not stopping.wait(1):
            for name,process in children:
                if process.poll() is not None:
                    logging.error('Processo %s encerrou; reiniciando o serviço.',name)
                    return process.returncode or 1
        return 0
    finally:
        for _,process in children:
            if process.poll() is None:
                process.terminate()
        for _,process in children:
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__=='__main__':
    sys.exit(main())
