"""Uma coleta por hora no minuto configurado (padrão: minuto 20)."""
import os
from datetime import datetime,timedelta,timezone


def collection_minute():
    try:
        minute=int(os.getenv('COLLECT_MINUTE','20'))
    except ValueError:
        minute=20
    return minute if 0<=minute<60 else 20


def next_collection(after):
    candidate=after.replace(minute=collection_minute(),second=0,microsecond=0)
    return candidate if candidate>after else candidate+timedelta(hours=1)


def is_stale(last_success,now=None):
    if not last_success:
        return True
    now=now or datetime.now(timezone.utc)
    return now>next_collection(last_success)+timedelta(minutes=15)
