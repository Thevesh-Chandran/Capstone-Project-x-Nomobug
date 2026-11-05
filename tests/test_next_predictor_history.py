import unittest
import pandas as pd
from scripts.test_next_predictors import previous_history
from scripts import benchmark_warranty_models as b


class HistoryTests(unittest.TestCase):
    def test_only_mature_same_pest_same_property_windows(self):
        f=pd.DataFrame({'address_hash':['A','A','A','A','B'],'normalized_pest_category':['ant','ant','ant','rodent','ant'],
            'anchor_date':pd.to_datetime(['2025-01-01','2025-01-20','2025-02-01','2025-01-01','2025-01-01']),
            'outcome_end_date':pd.to_datetime(['2025-01-31','2025-02-19','2025-03-03','2025-01-31','2025-01-31']),
            b.TARGET:[1,1,0,1,1]})
        out=previous_history(f)
        self.assertEqual(out.loc[1,'same_pest_past_windows'],0)
        self.assertEqual(out.loc[2,'same_pest_past_windows'],1)
        self.assertEqual(out.loc[2,'same_pest_past_return_windows'],1)
        self.assertTrue(pd.isna(out.loc[0,'same_pest_past_return_fraction']))

    def test_unknown_address_is_not_one_shared_property(self):
        f=pd.DataFrame({'address_hash':[None,None],'normalized_pest_category':['ant','ant'],
            'anchor_date':pd.to_datetime(['2025-01-01','2025-03-01']),
            'outcome_end_date':pd.to_datetime(['2025-01-31','2025-03-31']),b.TARGET:[1,0]})
        self.assertTrue(previous_history(f).isna().all().all())
