import os
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

os.environ['APP_BASE_URL']='https://eha.example.test'
os.environ['SECRET_KEY']='test-key-'*8
os.environ['GOOGLE_CLIENT_ID']='test-client'
os.environ['GOOGLE_CLIENT_SECRET']='test-secret'
from app import create_app


class AppTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app()
        self.app.config['TESTING']=True
        self.client=self.app.test_client()

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

    @patch('store.sync_status',return_value={'last':{'status':'ok'},'last_success':datetime.now(timezone.utc)})
    @patch('store.read_day',return_value=[dict(hour=7,soc_name='SOC A',operator='Ana',bips=8,shipments=3,
            exception_reason='Etiqueta',fluxo='FWD',sub_area='Reimpressão'),dict(hour=7,soc_name='SOC B',
            operator='Bia',bips=5,shipments=2,exception_reason='Etiqueta',fluxo='FWD',sub_area='Reimpressão')])
    @patch('store.catalog',return_value={'stations':['SOC A','SOC B']})
    def test_selected_station_keeps_network_matrix(self,*mocks):
        self.enter()
        result=self.client.get('/api/dashboard?day=2026-11-16&soc=SOC+A').get_json()
        self.assertEqual(result['bips'],8)
        self.assertEqual(sum(r['bips'] for r in result['matrix']),13)
        self.assertFalse(result['sync']['stale'])

    def test_bad_date_and_hour(self):
        self.enter()
        for query in ('day=bad','day=2026-11-16&hour=24','day=2026-11-16&hour=x'):
            self.assertEqual(self.client.get('/api/dashboard?'+query).status_code,400)

    def test_logout_csrf_and_seatalk_state(self):
        self.enter()
        self.assertEqual(self.client.post('/logout').status_code,400)
        self.assertEqual(self.client.get('/auth/seatalk/callback?code=x&state=wrong').status_code,403)
        self.enter()
        self.assertEqual(self.client.post('/logout',data={'csrf':'test-csrf'}).status_code,302)
        self.assertEqual(self.client.get('/api/catalog').status_code,401)


if __name__=='__main__':
    unittest.main()
