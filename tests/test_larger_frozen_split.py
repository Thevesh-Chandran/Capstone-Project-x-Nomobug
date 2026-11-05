import pandas as pd
from scripts.evaluate_larger_frozen_model import make_partitions


def test_agreed_date_split_purges_earlier_shared_groups():
    rows=[]
    for date,group,sale in [('2025-03-01','train','a'),('2025-03-02','v','b'),
       ('2025-03-03','t','c'),('2025-08-01','v','d'),('2025-08-02','t','e'),
       ('2026-02-01','t','f'),('2025-06-10','gap','g'),('2025-12-10','gap2','h')]:
        day=pd.Timestamp(date)
        rows.append({'anchor_date':day,'outcome_end_date':day+pd.Timedelta(days=30),
           'validation_group':group,'address_hash':group,'sales_record_id':sale})
    train,validation,test=make_partitions(pd.DataFrame(rows))
    assert train.sales_record_id.tolist()==['a']
    assert validation.sales_record_id.tolist()==['d']
    assert test.sales_record_id.tolist()==['f']
