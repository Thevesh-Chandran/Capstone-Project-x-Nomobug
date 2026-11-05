import copy
import pandas as pd
from scripts.research_premise_classifier import clean,dataset,partition

def test_target_and_billing_annotations_removed_from_text():
    assert 'commercial' not in clean('Example Commercial (Payment RM990)')
    assert 'payment' not in clean('Example Commercial (Payment RM990)')
    assert clean('Example Residential')==clean('Example Commercial')

def test_repeated_name_or_address_creates_same_reserved_group():
    source=[{'sales_record_id':'A','customer_name_raw':'Example Name','address_raw':'No 10 Jalan Test Taman Example','closed_date':'2025-01-01','premise_type':'RESIDENTIAL','include_in_sale_count':True},
            {'sales_record_id':'B','customer_name_raw':'Other Name','address_raw':'No 10 Jalan Test Taman Example','closed_date':'2026-01-01','premise_type':'COMMERCIAL','include_in_sale_count':True}]
    b={'records':{'sales':[{'sale_id':'A','customer_key':'one'},{'sale_id':'B','customer_key':'two'}]}}
    frame,_=dataset(source,b);assert frame.group.nunique()==1
    changed=copy.deepcopy(source);changed[0]['premise_type']='COMMERCIAL'
    second,_=dataset(changed,b);assert frame.text.tolist()==second.text.tolist()

def test_text_partition_has_no_customer_property_group_leakage():
    rows=pd.DataFrame([{'date':pd.Timestamp('2024-01-01')+pd.Timedelta(days=i),'group':str(i%75)} for i in range(150)])
    a,b,c,_=partition(rows)
    assert not(set(a.group)&set(b.group) or set(a.group)&set(c.group) or set(b.group)&set(c.group))
