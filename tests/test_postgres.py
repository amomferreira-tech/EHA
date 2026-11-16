"""Integração opt-in em banco dedicado, com rollback de todos os dados de teste."""
import os
import unittest
from datetime import date
from unittest.mock import patch
from domain import normalize
from store import connection, migrate, save_buckets
from test_domain import HEAD,row


@unittest.skipUnless(os.getenv('TEST_DATABASE_URL'),'Defina TEST_DATABASE_URL para um banco exclusivo de teste.')
class PostgresTests(unittest.TestCase):
    def test_idempotency_revision_and_missing_buckets(self):
        with patch.dict(os.environ,DATABASE_URL=os.environ['TEST_DATABASE_URL']):
            migrate()
            conn=connection()
            try:
                # Banco exclusivo. Não apagar dados de um ambiente compartilhado.
                count=conn.execute('SELECT count(*) AS n FROM eha_latest').fetchone()['n']
                self.assertEqual(count,0,'Use um banco de teste vazio.')
                run=conn.execute("INSERT INTO eha_runs(status) VALUES('running') RETURNING id").fetchone()['id']
                source=normalize([HEAD,row(),row(hour=8),row(soc='SOC B')])
                self.assertEqual(save_buckets(conn,run,source),3)
                self.assertEqual(save_buckets(conn,run,source),0)
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM eha_revisions').fetchone()['n'],3)
                correction=normalize([HEAD,row(bips=2)])
                self.assertEqual(save_buckets(conn,run,correction),1)
                latest=conn.execute('''SELECT sum(f.bips) AS n FROM eha_latest l
                    JOIN eha_facts f ON f.revision_id=l.revision_id''').fetchone()['n']
                self.assertEqual(latest,18)  # 2 corrigidos + 8 na outra hora + 8 no outro SOC.
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM eha_revisions').fetchone()['n'],4)
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM eha_latest').fetchone()['n'],3)
            finally:
                conn.rollback()
                conn.close()


if __name__=='__main__':
    unittest.main()
