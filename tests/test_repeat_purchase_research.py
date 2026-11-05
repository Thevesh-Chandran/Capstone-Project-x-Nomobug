import pandas as pd
from scripts.research_repeat_purchase import build


def customer(sales,identity='reviewed'):
    return {'identity_status':identity,'sales':sales}


def sale(date,programme,amount=100):
    return {'date':date,'programme_id':programme,'sales_rm':amount,'package':'1x','pest':'Ants','premise':'Residential'}


def test_later_upsell_is_not_new_programme_or_initial_feature():
    one,_=build([customer([sale('2026-01-01','A')])],'2026-10-11')
    upgraded,_=build([customer([sale('2026-01-01','A'),sale('2026-01-10','A',500)])],'2026-10-11')
    assert upgraded.iloc[0].repeat90==0
    assert one.iloc[0].log_initial_sales==upgraded.iloc[0].log_initial_sales


def test_repeat_outcome_uses_distinct_programme_within_ninety_days():
    rows,_=build([customer([sale('2026-01-01','A'),sale('2026-03-01','B')]),
                  customer([sale('2026-01-01','A'),sale('2026-05-01','B')])],'2026-10-11')
    assert list(rows.repeat90)==[1,0]
    assert all(rows.outcome_end<=pd.Timestamp('2026-10-11'))


def test_unknown_dates_identity_and_immature_windows_are_excluded():
    rows,audit=build([customer([sale(None,'A')]),customer([sale('2026-01-01','A')],'needs_review'),
                      customer([sale('2026-10-01','A')])],'2026-10-11')
    assert rows.empty
    assert audit['identity_review']==audit['immature']==audit['unknown_date_in_profile']==1
