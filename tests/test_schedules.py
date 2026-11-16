import unittest
from schedules import parse_starts,schedule,shift_totals


class ScheduleTests(unittest.TestCase):
    def test_rj4_cycle_from_first_t1_to_last_t3(self):
        result=schedule([7,15,23],True)
        self.assertEqual(result['hour_order'][0],7)
        self.assertEqual(result['hour_order'][-1],6)
        self.assertEqual([h for shift in result['shifts'] for h in shift['hours']],result['hour_order'])
        self.assertEqual(len(set(result['hour_order'])),24)

    def test_rj1_has_its_own_order(self):
        result=schedule([6,14,22],True)
        self.assertEqual(result['hour_order'],list(range(6,24))+list(range(6)))
        self.assertEqual(result['shifts'][2]['hours'],[22,23,0,1,2,3,4,5])

    def test_valid_unequal_shifts_and_midnight(self):
        result=schedule([22,6,15],True)
        self.assertEqual([len(s['hours']) for s in result['shifts']],[8,9,7])
        self.assertEqual(result['shifts'][0]['hours'],[22,23,0,1,2,3,4,5])

    def test_reject_overlaps_wrong_order_and_fractional_hours(self):
        for values in (['07:00','07:00','23:00'],['07:00','23:00','15:00'],
                       ['07:30','15:00','23:00'],['24:00','15:00','23:00'],['06:00','14:00']):
            with self.subTest(values=values),self.assertRaises(ValueError):
                parse_starts(values)
        self.assertEqual(parse_starts(['06:00','14:00','22:00']),[6,14,22])

    def test_turn_totals_preserve_rows_and_station(self):
        rows=[dict(soc_name='RJ1',hour=h,bips=10,shipments=5,fluxo='FWD',exception_reason='Etiqueta') for h in (6,13,14,21,22,5)]
        rows.append(dict(soc_name='RJ4',hour=6,bips=999,shipments=999,fluxo='FWD',exception_reason='Etiqueta'))
        totals=shift_totals(rows,'RJ1',schedule([6,14,22],True))
        self.assertEqual([s['bips'] for s in totals],[20,20,20])
        self.assertEqual(sum(s['shipments'] for s in totals),30)

    def test_unsaved_unit_has_no_invented_shift_groups(self):
        result=schedule()
        self.assertFalse(result['configured'])
        self.assertEqual(result['shifts'],[])


if __name__=='__main__':
    unittest.main()
