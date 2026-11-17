import os
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

os.environ['APP_BASE_URL']='https://eha.example.test'
os.environ['SECRET_KEY']='test-key-'*8
os.environ['GOOGLE_CLIENT_ID']='test-client'
os.environ['GOOGLE_CLIENT_SECRET']='test-secret'
from app import create_app
from schedules import schedule


class AppTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app()
        self.app.config['TESTING']=True
        self.client=self.app.test_client()
        schedule_mock=patch('store.unit_schedule',return_value=schedule())
        schedule_mock.start()
        self.addCleanup(schedule_mock.stop)

    def enter(self,email='test@shopee.com',hd='shopee.com',verified=True):
        with self.client.session_transaction() as session:
            session['user']={'sub':'test','email':email,'hd':hd,'email_verified':verified}
            session['csrf']='test-csrf'
            session['station']='*'

    def test_health_and_private_api(self):
        self.assertEqual(self.client.get('/healthz').status_code,200)
        self.assertEqual(self.client.get('/api/catalog').status_code,401)
        self.assertEqual(self.client.get('/').status_code,302)

    def test_unverified_or_wrong_domain_denied(self):
        for email,hd,verified in [('user@gmail.com','gmail.com',True),('test@shopee.com','shopee.com',False),
                                  ('test@shopee.com','evil.test',True)]:
            self.enter(email,hd,verified)
            self.assertEqual(self.client.get('/api/catalog').status_code,401)

    @patch('store.catalog',return_value={'stations':['SOC A'],'days':['2026-11-16'],'flows':[],'subareas':[]})
    @patch('store.preference')
    def test_station_requires_csrf_and_known_station(self,pref,cat):
        self.enter()
        self.assertEqual(self.client.post('/station',data={'station':'SOC A'}).status_code,400)
        self.assertEqual(self.client.post('/station',data={'station':'BAD','csrf':'test-csrf'}).status_code,400)
        self.assertEqual(self.client.post('/station',data={'station':'SOC A','csrf':'test-csrf'}).status_code,302)
        pref.assert_called_once_with('test@shopee.com','SOC A')

    @patch('store.coverage',return_value=[])
    @patch('store.sync_status',return_value={'last':{'status':'ok'},'last_success':datetime.now(timezone.utc)})
    @patch('store.read_day',return_value=[dict(hour=7,soc_name='SOC A',operator='Ana',bips=8,shipments=3,
            exception_reason='Etiqueta',fluxo='FWD',sub_area='Reimpressão'),dict(hour=7,soc_name='SOC B',
            operator='Bia',bips=5,shipments=2,exception_reason='Etiqueta',fluxo='FWD',sub_area='Reimpressão')])
    @patch('store.catalog',return_value={'stations':['SOC A','SOC B']})
    def test_selected_station_contains_only_that_soc(self,*mocks):
        self.enter()
        result=self.client.get('/api/dashboard?day=2026-11-16&soc=SOC+A').get_json()
        self.assertEqual(result['bips'],8)
        self.assertEqual(sum(r['bips'] for r in result['matrix']),8)
        self.assertEqual([r['soc'] for r in result['matrix']],['SOC A'])
        self.assertEqual([r['name'] for r in result['people']],['Ana'])
        self.assertEqual(result['available_reasons'],['Etiqueta'])
        self.assertFalse(result['sync']['stale'])
        requested_network=self.client.get('/api/dashboard?view=overall&day=2026-11-16&soc=SOC+A').get_json()
        self.assertEqual(requested_network['view'],'soc')
        self.assertEqual([r['soc'] for r in requested_network['matrix']],['SOC A'])

    def test_email_login_comes_before_seatalk(self):
        with patch.dict(os.environ,SEATALK_APP_ID='fixture-app',SEATALK_APP_SECRET='fixture-secret'):
            client=create_app().test_client()
            html=client.get('/login').get_data(as_text=True)
            self.assertLess(html.index('href="/auth/google"'),html.index('href="/auth/seatalk"'))
            self.assertIn('Entrar com e-mail corporativo',html)

    @patch('store.coverage',return_value=[])
    @patch('store.sync_status',return_value={'last':{'status':'ok'},'last_success':datetime.now(timezone.utc)})
    @patch('store.read_overall',return_value=[dict(soc_name='SOC A',hour=7,bips=8),dict(soc_name='SOC B',hour=8,bips=5)])
    @patch('store.catalog',return_value={'stations':['SOC A','SOC B']})
    def test_overall_returns_only_hourly_production(self,*mocks):
        self.enter()
        result=self.client.get('/api/dashboard?view=overall&day=2026-11-16').get_json()
        self.assertEqual(result['bips'],13)
        self.assertEqual(len(result['matrix']),2)
        for key in ('people','reasons','subareas','flows'):
            self.assertNotIn(key,result)

    @patch('store.catalog',return_value={'stations':['SOC A']})
    def test_soc_view_requires_station(self,*mocks):
        self.enter()
        self.assertEqual(self.client.get('/api/dashboard?view=soc&day=2026-11-16').status_code,400)

    def test_dashboard_has_real_tabs_and_no_subarea(self):
        self.enter()
        text=self.client.get('/').get_data(as_text=True)
        self.assertIn('role="tabpanel"',text)
        self.assertIn('data-searchable id="soc"',text)
        self.assertIn('id="app-sidebar"',text)
        self.assertIn('href="/about"',text)
        self.assertNotIn('subarea',text.lower())

    @patch('store.catalog',return_value={'stations':['SOC A','SOC B']})
    @patch('store.save_unit_schedule')
    def test_settings_are_per_station_and_require_csrf(self,save,cat):
        self.enter()
        self.assertEqual(self.client.get('/settings?soc=SOC+A').status_code,200)
        self.assertEqual(self.client.post('/settings',data={'soc':'SOC A','shift_start':['06:00','14:00','22:00']}).status_code,400)
        response=self.client.post('/settings',data={'soc':'SOC A','csrf':'test-csrf','version':'0',
            'shift_start':['06:00','14:00','22:00']})
        self.assertEqual(response.status_code,302)
        save.assert_called_once_with('SOC A',[6,14,22],'test@shopee.com',0)

    @patch('store.catalog',return_value={'stations':['SOC A']})
    @patch('store.save_unit_schedule')
    def test_settings_reject_invalid_turns(self,save,cat):
        self.enter()
        response=self.client.post('/settings',data={'soc':'SOC A','csrf':'test-csrf','version':'0',
            'shift_start':['06:00','06:00','22:00']})
        self.assertEqual(response.status_code,400)
        save.assert_not_called()
        self.assertEqual(self.client.get('/settings?soc=BAD').status_code,400)

    @patch('store.coverage',return_value=[])
    @patch('store.sync_status',return_value={'last':{'status':'ok'},'last_success':datetime.now(timezone.utc)})
    @patch('store.read_day',return_value=[dict(soc_name='SOC A',hour=h,operator='Ana',bips=10,shipments=4,
        fluxo='FWD',exception_reason='Etiqueta') for h in (6,13,14,21,22,5)])
    @patch('store.catalog',return_value={'stations':['SOC A']})
    def test_turn_filter_and_graph_order(self,*mocks):
        self.enter()
        with patch('store.unit_schedule',return_value=schedule([6,14,22],True)):
            data=self.client.get('/api/dashboard?day=2026-11-16&soc=SOC+A&shift=t3').get_json()
            self.assertEqual(data['bips'],20)
            self.assertEqual(data['schedule']['hour_order'][0],6)
            self.assertEqual(data['schedule']['hour_order'][-1],5)
            self.assertEqual([s['bips'] for s in data['shift_totals']],[20,20,20])
            self.assertEqual(sum(h['bips'] for h in data['daily_series']),60)
            self.assertEqual(self.client.get('/api/dashboard?day=2026-11-16&soc=SOC+A&shift=t4').status_code,400)

    def test_bad_date_and_hour(self):
        self.enter()
        for query in ('day=bad','day=2026-11-16&hour=24','day=2026-11-16&hour=x'):
            self.assertEqual(self.client.get('/api/dashboard?'+query).status_code,400)

    def test_anonymous_api_does_not_erase_pending_oauth(self):
        with self.client.session_transaction() as session:
            session['_state_google_pending']={'nonce':'pending-nonce'}
        self.assertEqual(self.client.get('/api/catalog').status_code,401)
        with self.client.session_transaction() as session:
            self.assertEqual(session['_state_google_pending']['nonce'],'pending-nonce')

    def test_about_requires_login_and_identifies_owner(self):
        self.assertEqual(self.client.get('/about').status_code,302)
        self.enter()
        response=self.client.get('/about')
        self.assertEqual(response.status_code,200)
        self.assertIn('Amom Ferreira de Paula',response.get_data(as_text=True))
        self.assertIn('mailto:amom.ferreira@shopee.com',response.get_data(as_text=True))

    def test_seatalk_native_requires_origin_challenge_and_verified_profile(self):
        profile={'provider':'seatalk','identity_verified':True,'sub':'seatalk:verified',
                 'email':'test@shopee.com','name':'Teste'}
        with patch.dict(os.environ,SEATALK_APP_ID='fixture-app',SEATALK_APP_SECRET='fixture-secret'):
            client=create_app().test_client()
            challenge=client.get('/auth/seatalk/native/challenge').get_json()['state']
            with patch('seatalk_login.employee_from_sso',return_value=profile) as verify:
                payload={'state':challenge,'token':'fixture-temporary-token'}
                self.assertEqual(client.post('/auth/seatalk/native',json=payload).status_code,400)
                response=client.post('/auth/seatalk/native',json=payload,headers={'Origin':'https://eha.example.test'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.get_json()['redirect'],'/station')
                verify.assert_called_once_with('fixture-temporary-token')
                self.assertEqual(client.post('/auth/seatalk/native',json=payload,headers={'Origin':'https://eha.example.test'}).status_code,400)

    def test_seatalk_internal_login_does_not_show_google_outbound_link(self):
        with patch.dict(os.environ,SEATALK_APP_ID='fixture-app',SEATALK_APP_SECRET='fixture-secret'):
            client=create_app().test_client()
            native=client.get('/login',headers={'User-Agent':'Mozilla/5.0 SeaTalk/2.0'}).get_data(as_text=True)
            self.assertIn('data-seatalk-native',native)
            self.assertIn('Abrir no navegador',native)
            self.assertNotIn('href="/auth/google"',native)
            browser=client.get('/login?browser=1',headers={'User-Agent':'Mozilla/5.0 SeaTalk/2.0'}).get_data(as_text=True)
            self.assertIn('href="/auth/google"',browser)

    def test_logout_csrf_and_seatalk_state(self):
        self.enter()
        self.assertEqual(self.client.post('/logout').status_code,400)
        self.assertEqual(self.client.get('/auth/seatalk/callback?code=x&state=wrong').status_code,403)
        self.enter()
        self.assertEqual(self.client.post('/logout',data={'csrf':'test-csrf'}).status_code,302)
        self.assertEqual(self.client.get('/api/catalog').status_code,401)


if __name__=='__main__':
    unittest.main()
