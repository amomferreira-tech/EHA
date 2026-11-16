import unittest
from domain import normalize, summarize, fingerprint,overall

HEAD = ['year_resolved','month_resolved','week_resolved','cutoff','hora_resolucao','soc_name',
        'exception_reason','operator','fluxo','resolved_shipment','resolved_bips','sub_area','before_station_type']


def row(day='2026-11-16',hour=7,soc='SOC A',operator='Pessoa A',bips=8,shipments=3,reason='Etiqueta'):
    return [2026,11,47,day,hour,soc,reason,operator,'FWD',shipments,bips,'Reimpressão','SOC']


class DomainTests(unittest.TestCase):
    def test_count_bips_and_preserve_cutoff(self):
        buckets=normalize([HEAD,row(hour=2),row(hour=2,bips=2)])
        records=buckets[('2026-11-16',2,'SOC A')]
        self.assertEqual(records[0]['bips'],10)
        self.assertEqual(records[0]['shipments'],6)

    def test_order_independent_fingerprint(self):
        a=normalize([HEAD,row(),row(operator='B')])
        b=normalize([HEAD,row(operator='B'),row()])
        self.assertEqual(fingerprint(next(iter(a.values()))),fingerprint(next(iter(b.values()))))

    def test_reject_entire_invalid_load(self):
        for bad in [row(hour=24),row(bips=''),row(bips=-2),row(bips='1.5'),row(soc=''),row(day='16-11-26')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                normalize([HEAD,row(),bad])

    def test_sheet_serial_day_and_reordered_columns(self):
        values=row(day=46342)
        from datetime import date, timedelta
        expected=(date(1899,12,30)+timedelta(days=46342)).isoformat()
        result=normalize([list(reversed(HEAD)),list(reversed(values))])
        self.assertIn((expected,7,'SOC A'),result)

    def test_station_hour_details_and_missing_hour(self):
        buckets=normalize([HEAD,row(),row(hour=8,bips=5),row(soc='SOC B',bips=2),row(reason='Avaria',bips=4)])
        rows=[dict(r,hour=key[1]) for key,records in buckets.items() for r in records]
        result=summarize(rows,['SOC A','SOC B'],'2026-11-16',soc='SOC A',hour=7)
        self.assertEqual(result['bips'],12)
        self.assertEqual(result['operators'],1)
        self.assertEqual(len(result['people'][0]['reasons']),2)
        self.assertIsNone(result['matrix'][0]['hours'][8])
        self.assertFalse(result['series'][8]['observed'])

    def test_explicit_zero_is_observed(self):
        records=normalize([HEAD,row(bips=0,shipments=0)])
        result=summarize([dict(r,hour=7) for r in next(iter(records.values()))],['SOC A'],'2026-11-16')
        self.assertTrue(result['series'][7]['observed'])
        self.assertEqual(result['matrix'][0]['hours'][7],0)

    def test_pareto_uses_exception_reason_and_not_sub_area(self):
        a=row(reason='Etiqueta avariada',bips=70)
        b=row(reason='Reembalagem',bips=20)
        c=row(reason='Outros',bips=10)
        a[11]=b[11]=c[11]='Campo interno que não é motivo'
        source=normalize([HEAD,a,b,c])
        rows=[dict(r,hour=7) for rs in source.values() for r in rs]
        result=summarize(rows,['SOC A'],'2026-11-16',soc='SOC A')
        self.assertEqual([r['name'] for r in result['reasons']],['Etiqueta avariada','Reembalagem','Outros'])
        self.assertEqual([r['cumulative'] for r in result['reasons']],[.7,.9,1])
        self.assertEqual(sum(r['bips'] for r in result['reasons']),result['bips'])
        detail=summarize(rows,['SOC A'],'2026-11-16',soc='SOC A',reason='Reembalagem')
        self.assertEqual(detail['bips'],20)

    def test_source_does_not_require_sub_area_column(self):
        header=HEAD[:11]+HEAD[12:]
        source_row=row()
        result=normalize([header,source_row[:11]+source_row[12:]])
        record=next(iter(result.values()))[0]
        self.assertEqual(record['exception_reason'],'Etiqueta')
        self.assertEqual(record['bips'],8)

    def test_overall_keeps_missing_distinct_from_zero(self):
        result=overall([dict(soc_name='A',hour=2,bips=0)],['A','B'],'2026-11-16')
        station=next(r for r in result['matrix'] if r['soc']=='A')
        self.assertEqual(station['hours'][2],0)
        self.assertIsNone(station['hours'][1])


if __name__=='__main__':
    unittest.main()
