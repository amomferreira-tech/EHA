"""Login with SeaTalk segundo a documentação oficial da plataforma."""
import os
import threading
import time
import requests

_lock = threading.Lock()
_token = None
_expires_at = 0


def configured():
    return bool(os.getenv("SEATALK_APP_ID") and os.getenv("SEATALK_APP_SECRET"))


def app_token():
    global _token, _expires_at
    with _lock:
        if _token and time.time() < _expires_at - 60:
            return _token
        response = requests.post("https://openapi.seatalk.io/auth/app_access_token",
            json={"app_id": os.environ["SEATALK_APP_ID"], "app_secret": os.environ["SEATALK_APP_SECRET"]},
            timeout=(5, 20), allow_redirects=False)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("code") != 0 or not data.get("app_access_token"):
            raise RuntimeError("SeaTalk não autorizou o aplicativo.")
        expiry = float(data.get("expire", 0))
        if expiry <= time.time():
            raise RuntimeError("Token do aplicativo SeaTalk expirado.")
        _token, _expires_at = data["app_access_token"], expiry
        return _token


def employee_from_code(code):
    response = requests.get("https://openapi.seatalk.io/open_login/code2employee",
        params={"code": code}, headers={"Authorization": "Bearer " + app_token()},
        timeout=(5, 20), allow_redirects=False)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("code") != 0:
        raise ValueError("Código de autorização SeaTalk inválido ou expirado.")
    profile = data.get("employee")
    if not isinstance(profile, dict) or not profile.get("employee_code") or not profile.get("email"):
        raise ValueError("O SeaTalk não forneceu o e-mail corporativo necessário para autorizar o acesso.")
    # Avatar, celular e outros dados desnecessários não são armazenados na sessão.
    return {"provider": "seatalk", "identity_verified": True,
            "sub": "seatalk:" + os.environ["SEATALK_APP_ID"] + ":" + str(profile["employee_code"]),
            "email": str(profile["email"]).strip().lower(), "name": str(profile.get("name") or profile["email"])}
