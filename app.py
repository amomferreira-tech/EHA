import logging
import os
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

from authlib.integrations.flask_client import OAuth
from flask import Flask, jsonify, redirect, render_template, request, session, abort
import store
import seatalk_login
from domain import summarize,overall


def create_app():
    app = Flask(__name__)
    base = os.getenv('APP_BASE_URL','').rstrip('/')
    secret = os.getenv('SECRET_KEY','')
    domains = {s.strip().lower() for s in os.getenv('ALLOWED_GOOGLE_DOMAINS','shopee.com,shopeemobile-external.com').split(',') if s.strip()}
    emails = {s.strip().lower() for s in os.getenv('ALLOWED_EMAILS','').split(',') if s.strip()}
    configured = bool(len(secret)>=32 and urlparse(base).scheme=='https' and urlparse(base).netloc)
    google_ready = configured and bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'))
    sea_ready = configured and seatalk_login.configured()
    app.config.update(SECRET_KEY=secret or secrets.token_hex(32), SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=16384)
    oauth = OAuth(app)
    google = oauth.register('google',client_id=os.getenv('GOOGLE_CLIENT_ID'),client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope':'openid email profile', 'timeout':20})

    def allowed(user):
        email = str(user.get('email','')).strip().lower()
        identity = (user.get('identity_verified') is True if user.get('provider')=='seatalk'
                    else user.get('email_verified') is True)
        domain_ok = email.rsplit('@',1)[-1] in domains
        if user.get('provider')!='seatalk':
            domain_ok = domain_ok and str(user.get('hd','')).lower() in domains
        return bool(user.get('sub') and identity and (domain_ok or email in emails))

    def protected(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            if not configured or not allowed(session.get('user',{})):
                session.clear()
                return (jsonify(error='Entre novamente para continuar.'),401) if request.path.startswith('/api/') else redirect('/login')
            return fn(*args,**kwargs)
        return wrapped

    def csrf():
        if not session.get('csrf') or not secrets.compare_digest(session['csrf'],request.form.get('csrf','')):
            abort(400)

    def begin_session(user):
        session.clear()
        session.permanent=True
        session['user']=user
        session['csrf']=secrets.token_urlsafe(32)
        return redirect('/station')

    @app.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store, private'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        scripts = "'self' https://static.cdn.haiserve.com" if request.endpoint=='sea' else "'self'"
        images = "'self' data: https://static.cdn.haiserve.com" if request.endpoint=='sea' else "'self' data:"
        response.headers['Content-Security-Policy']=(f"default-src 'self'; script-src {scripts}; style-src 'self' 'unsafe-inline'; "
            f"img-src {images}; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
        response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.get('/healthz')
    def health():
        return jsonify(status='ok')

    @app.get('/login')
    def login():
        return render_template('login.html',google_ready=google_ready,sea_ready=sea_ready), (200 if google_ready or sea_ready else 503)

    @app.get('/auth/google')
    def google_login():
        if not google_ready:
            return redirect('/login')
        session.clear()
        return google.authorize_redirect(base+'/auth/callback',prompt='select_account')

    @app.get('/auth/callback')
    def callback():
        if not google_ready:
            return redirect('/login')
        try:
            user=google.authorize_access_token().get('userinfo',{})
            if not allowed(user):
                raise ValueError('Identidade não autorizada')
            return begin_session({k:user.get(k) for k in ('sub','email','name','hd','email_verified')})
        except Exception as exc:
            logging.warning('Login recusado: %s',type(exc).__name__)
            session.clear()
            return render_template('login.html',google_ready=google_ready,sea_ready=sea_ready,denied=True),403

    @app.get('/auth/seatalk')
    def sea():
        if not sea_ready:
            return redirect('/login')
        session.clear()
        session['seatalk_state']=secrets.token_urlsafe(32)
        session['seatalk_started']=time.time()
        return render_template('seatalk.html',app_id=os.environ['SEATALK_APP_ID'],
            callback_url=base+'/auth/seatalk/callback',state=session['seatalk_state'])

    @app.get('/auth/seatalk/callback')
    def sea_callback():
        try:
            state=session.pop('seatalk_state','')
            started=session.pop('seatalk_started',0)
            code=request.args.get('code','')
            if not sea_ready or not state or not secrets.compare_digest(state,request.args.get('state','')):
                raise ValueError('State inválido')
            if time.time()-started>600 or not 1<=len(code)<=2048:
                raise ValueError('Código inválido')
            user=seatalk_login.employee_from_code(code)
            if not allowed(user):
                raise ValueError('Identidade não autorizada')
            return begin_session(user)
        except Exception as exc:
            logging.warning('SeaTalk recusado: %s',type(exc).__name__)
            session.clear()
            return render_template('login.html',google_ready=google_ready,sea_ready=sea_ready,denied=True),403

    @app.post('/logout')
    @protected
    def logout():
        csrf()
        session.clear()
        return redirect('/login')

    @app.route('/station', methods=['GET','POST'])
    @protected
    def station():
        stations=store.catalog()['stations']
        if request.method=='POST':
            csrf()
            selected=request.form.get('station','')
            if selected!='*' and selected not in stations:
                abort(400)
            store.preference(session['user']['email'],selected)
            session['station']=selected
            return redirect('/')
        return render_template('station.html',stations=stations,
                    selected=store.preference(session['user']['email']),csrf=session['csrf'])

    @app.get('/')
    @protected
    def index():
        if not session.get('station'):
            return redirect('/station')
        return render_template('dashboard.html',user=session['user'],csrf=session['csrf'],station=session['station'])

    @app.get('/api/catalog')
    @protected
    def catalog():
        return jsonify(store.catalog())

    @app.get('/api/dashboard')
    @protected
    def dashboard():
        day=request.args.get('day','')
        try:
            date.fromisoformat(day)
            h=request.args.get('hour','')
            hour=int(h) if h else None
            if hour is not None and not 0<=hour<=23:
                raise ValueError()
        except ValueError:
            return jsonify(error='Data ou hora inválida.'),400
        cat=store.catalog()
        soc=request.args.get('soc','')
        if soc and soc not in cat['stations']:
            return jsonify(error='Estação inválida.'),400
        view='soc' if soc else request.args.get('view','overall')
        if view not in ('soc','overall') or (view=='soc' and not soc):
            return jsonify(error='Escolha uma estação para abrir a visão do SOC.'),400
        if view=='overall':
            result=overall(store.read_overall(day),cat['stations'],day)
        else:
            rows=store.read_day(day,soc)
            flow=request.args.get('flow','')
            reason=request.args.get('reason','')
            result=summarize(rows,[soc],day,soc,flow,hour,reason)
            result['daily_series']=summarize(rows,[soc],day,soc,flow,reason=reason)['series']
            result['available_reasons']=sorted({r['exception_reason'] or 'Não informado' for r in rows})
            result['available_flows']=sorted({r['fluxo'] for r in rows if r['fluxo']})
            result['soc']=soc
            result['hour']=hour
        result['view']=view
        result['coverage']=store.coverage(day,soc if view=='soc' else '')
        status=store.sync_status()
        good=status['last_success']
        result['sync']={'last_success':good.isoformat() if good else None,
            'error':status['last'].get('error') if status['last'] and status['last']['status']=='error' else None,
            'failed':bool(status['last'] and status['last']['status']=='error'),
            'stale':not good or (datetime.now(timezone.utc)-good).total_seconds()>max(900,int(os.getenv('SYNC_SECONDS','300'))*3)}
        return jsonify(result)

    @app.errorhandler(500)
    def unavailable(exc):
        if request.path.startswith('/api/'):
            return jsonify(error='Dados temporariamente indisponíveis. Tente novamente.'),503
        return render_template('unavailable.html'),503

    return app


app=create_app()
