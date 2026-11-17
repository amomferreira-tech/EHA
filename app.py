import logging
import hashlib
import re
import os
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse,quote

from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import MismatchingStateError
from flask import Flask, jsonify, redirect, render_template, request, session, abort
import store
import seatalk_login
from domain import summarize,overall
from schedules import parse_starts,shift_totals,hour_calendar


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
                # Não apagar state/nonce de uma entrada anônima em andamento.
                if session.get('user'):
                    session.clear()
                return (jsonify(error='Entre novamente para continuar.'),401) if request.path.startswith('/api/') else redirect('/login')
            return fn(*args,**kwargs)
        return wrapped

    def csrf():
        if not session.get('csrf') or not secrets.compare_digest(session['csrf'],request.form.get('csrf','')):
            abort(400)

    def remember_callback(provider,state):
        session['last_login']={'provider':provider,'state_hash':hashlib.sha256(state.encode()).hexdigest(),'completed':time.time()}

    def completed_callback(provider):
        recent=session.get('last_login',{})
        state=request.args.get('state','')
        return (allowed(session.get('user',{})) and bool(state) and recent.get('provider')==provider
            and 0<=time.time()-recent.get('completed',0)<=120
            and secrets.compare_digest(recent.get('state_hash',''),hashlib.sha256(state.encode()).hexdigest()))

    def begin_session(user,provider='',state=''):
        session.clear()
        session.permanent=True
        session['user']=user
        session['csrf']=secrets.token_urlsafe(32)
        if provider and state:
            remember_callback(provider,state)
        return redirect('/station')

    def prepare_login():
        if session.get('user'):
            session.clear()

    def start_google_login(recovery=False):
        prepare_login()
        state=('g1.' if recovery else 'g0.')+secrets.token_urlsafe(32)
        return google.authorize_redirect(base+'/auth/callback',state=state,
            **({} if recovery else {'prompt':'select_account'}))

    @app.context_processor
    def shell_context():
        native=bool(re.search(r'(?:^|\s)SeaTalk(?:\.rc)?/',request.headers.get('User-Agent',''),re.I))
        soc=request.args.get('soc','') or session.get('station','')
        if soc=='*':
            soc=''
        return dict(seatalk_native_view=native and request.args.get('browser')!='1',
            shell_soc=soc,shell_user=session.get('user',{}),shell_csrf=session.get('csrf',''),
            shell_page='settings' if request.path=='/settings' else 'about' if request.path=='/about' else
                'overall' if request.path=='/network' else 'soc' if request.path=='/soc' else 'overall' if not soc else 'soc')

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
        if allowed(session.get('user',{})):
            return redirect('/')
        return render_template('login.html',google_ready=google_ready,sea_ready=sea_ready), (200 if google_ready or sea_ready else 503)

    @app.get('/auth/google')
    def google_login():
        if not google_ready:
            return redirect('/login')
        return start_google_login()

    @app.get('/auth/callback')
    def callback():
        if not google_ready:
            return redirect('/login')
        if completed_callback('google'):
            return redirect('/')
        try:
            user=google.authorize_access_token().get('userinfo',{})
            if not allowed(user):
                raise PermissionError('Identidade não autorizada')
            return begin_session({k:user.get(k) for k in ('sub','email','name','hd','email_verified')},'google',request.args.get('state',''))
        except MismatchingStateError:
            # Nova autorização completa, com state/nonce novos; nunca aceitar código sem state.
            if not request.args.get('state','').startswith('g1.'):
                try:
                    return start_google_login(recovery=True)
                except Exception as exc:
                    logging.warning('Recuperação Google indisponível: %s',type(exc).__name__)
            return render_template('login.html',google_ready=google_ready,sea_ready=sea_ready,
                auth_error='Não foi possível manter sua sessão de entrada. Use Abrir no navegador e tente novamente.'),503
        except PermissionError:
            session.clear()
            return render_template('login.html',google_ready=google_ready,sea_ready=sea_ready,denied=True),403
        except Exception as exc:
            logging.warning('Login recusado: %s',type(exc).__name__)
            return render_template('login.html',google_ready=google_ready,sea_ready=sea_ready,
                auth_error='Não foi possível concluir a entrada agora. Tente novamente em instantes.'),503

    @app.get('/auth/seatalk/native/challenge')
    def sea_native_challenge():
        if not sea_ready:
            return jsonify(error='A entrada SeaTalk está aguardando configuração.'),503
        session['seatalk_native_state']=secrets.token_urlsafe(32)
        session['seatalk_native_started']=time.time()
        return jsonify(state=session['seatalk_native_state'])

    @app.post('/auth/seatalk/native')
    def sea_native_login():
        if request.headers.get('Origin')!=base or not request.is_json:
            return jsonify(error='Solicitação de entrada inválida.'),400
        payload=request.get_json(silent=True)
        expected=session.pop('seatalk_native_state','')
        started=session.pop('seatalk_native_started',0)
        if not isinstance(payload,dict):
            return jsonify(error='Solicitação de entrada inválida.'),400
        state,token=payload.get('state'),payload.get('token')
        if (not sea_ready or not expected or not isinstance(state,str) or not secrets.compare_digest(expected,state)
                or not 0<=time.time()-started<=300 or not isinstance(token,str) or not 1<=len(token)<=8192):
            return jsonify(error='Sua tentativa expirou. Tente entrar novamente.'),400
        try:
            user=seatalk_login.employee_from_sso(token)
            if not allowed(user):
                return jsonify(error='Sua conta não tem acesso ao EHA Live. Use sua conta corporativa autorizada.'),403
            begin_session(user)
            return jsonify(redirect='/station')
        except Exception as exc:
            logging.warning('Entrada nativa SeaTalk indisponível: %s',type(exc).__name__)
            return jsonify(error='O SeaTalk não concluiu a entrada. Tente novamente ou use Abrir no navegador.'),503

    @app.get('/auth/seatalk')
    def sea():
        if not sea_ready:
            return redirect('/login')
        if shell_context()['seatalk_native_view']:
            return render_template('login.html',google_ready=google_ready,sea_ready=sea_ready)
        prepare_login()
        session['seatalk_state']=secrets.token_urlsafe(32)
        session['seatalk_started']=time.time()
        return render_template('seatalk.html',app_id=os.environ['SEATALK_APP_ID'],
            callback_url=base+'/auth/seatalk/callback',state=session['seatalk_state'])

    @app.get('/auth/seatalk/callback')
    def sea_callback():
        if completed_callback('seatalk'):
            return redirect('/')
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
            return begin_session(user,'seatalk',request.args.get('state',''))
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
        cat=store.catalog()
        stations=cat['stations']
        if request.method=='POST':
            csrf()
            selected=request.form.get('station','')
            if selected!='*' and selected not in stations:
                abort(400)
            store.preference(session['user']['email'],selected)
            session['station']=selected
            return redirect('/')
        return render_template('station.html',stations=stations,station_codes=cat.get('station_codes',{}),
                    selected=store.preference(session['user']['email']),csrf=session['csrf'])

    @app.get('/')
    @app.get('/network')
    @app.get('/soc')
    @protected
    def index():
        if not session.get('station'):
            return redirect('/station')
        return render_template('dashboard.html',user=session['user'],csrf=session['csrf'],
            station='*' if request.path=='/network' else session['station'])

    @app.get('/about')
    @protected
    def about():
        return render_template('about.html')

    @app.get('/api/catalog')
    @protected
    def catalog():
        return jsonify(store.catalog())

    @app.route('/settings',methods=['GET','POST'])
    @protected
    def settings():
        cat=store.catalog()
        stations=cat['stations']
        soc=request.form.get('soc','') if request.method=='POST' else request.args.get('soc','')
        if not soc and session.get('station') in stations:
            soc=session['station']
        if soc and soc not in stations:
            abort(400)
        definition=store.unit_schedule(soc) if soc else None
        error=None
        values=[f'{h:02d}:00' for h in definition['starts']] if definition and definition['configured'] else [f"{definition['starts'][0]:02d}:00" if definition else '06:00','','']
        if request.method=='POST':
            csrf()
            if not soc:
                abort(400)
            values=request.form.getlist('shift_start')
            try:
                starts=parse_starts(values)
                expected=int(request.form.get('version','-1'))
                store.save_unit_schedule(soc,starts,session['user']['email'],expected)
                return redirect('/settings?soc='+quote(soc,safe='')+'&saved=1')
            except ValueError as exc:
                error=str(exc)
        return render_template('settings.html',user=session['user'],csrf=session['csrf'],
            stations=stations,station_codes=cat.get('station_codes',{}),soc=soc,definition=definition,values=values,error=error,
            saved=request.args.get('saved')=='1'),400 if error else 200

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
            definition=store.unit_schedule(soc)
            shift_id=request.args.get('shift','')
            selected=next((s for s in definition['shifts'] if s['id']==shift_id),None) if shift_id else None
            if shift_id and not selected:
                return jsonify(error='Turno não configurado para esta unidade.'),400
            selected_rows=[r for r in rows if r['hour'] in selected['hours']] if selected else rows
            result=summarize(selected_rows,[soc],day,soc,flow,hour,reason)
            result['daily_series']=summarize(rows,[soc],day,soc,flow,reason=reason)['series']
            for series in (result['series'],result['daily_series']):
                for item in series:
                    item.update(hour_calendar(day,item['hour'],definition['starts'][0]))
            result['schedule']=definition
            result['shift']=shift_id
            result['shift_totals']=shift_totals(rows,soc,definition,flow,reason)
            result['available_reasons']=sorted({r['exception_reason'] or 'Não informado' for r in rows})
            result['available_flows']=sorted({r['fluxo'] for r in rows if r['fluxo']})
            result['soc']=soc
            result['soc_code']=cat.get('station_codes',{}).get(soc,'')
            result['hour']=hour
        result['view']=view
        result['station_codes']=cat.get('station_codes',{})
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
