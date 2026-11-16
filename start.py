import os
import subprocess
import sys

from store import migrate

migrate()
sys.exit(subprocess.call(["gunicorn", "app:app", "--bind", f"0.0.0.0:{os.getenv('PORT', '8080')}",
                          "--workers", "2", "--threads", "4", "--timeout", "60",
                          "--access-logfile", "-", "--access-logformat", "%(h)s %(m)s %(U)s %(s)s"]))
