from webapp.business import build, aggregate
import pytest


@pytest.mark.parametrize('start,end',[('2026-02-30','2026-03-01'),('2026-10-20','2026-10-01'),('2026-01-01',''),('20260101','2026-10-01')])
def test_area_filters_reject_invalid_or_reversed_dates(start,end):
    from webapp.business import radius
    with pytest.raises(ValueError):radius({'sales':[],'appointments':[]},3,101,5,start,end)


def test_area_sales_keep_unknown_amount_coverage():
    from webapp.business import radius
    result=radius({'sales':[{'date':'2026-10-01','sales_rm':None,
        'location':{'latitude':3,'longitude':101,'uncertainty_km':0}}],'appointments':[]},3,101,5)
    assert result['sale_rows']==1 and result['unknown_sale_values']==1


def sale(sid, name='Client', phone='0123456789', amount=100):
    return dict(sales_row_id=sid,sales_record_id='C'+str(sid),include_in_sale_count=True,
        sale_total_rm=amount,closed_date='2026-10-01',customer_name_raw=name,phone_raw=phone)


def test_programme_upsell_is_one_purchase_and_later_contract_is_repeat():
    s,c=build([sale(1),sale(2),sale(3)],[],{'C1':'upgrade','C2':'upgrade'},lambda r:None)
    assert len(c)==1 and c[0]['purchase_count']==2 and c[0]['repeat_customer']
    assert c[0]['sales_rm']==300 and s['coverage']['sale_rows']==3


def test_shared_phone_does_not_merge_companies_or_missing_identities():
    s,c=build([sale(1,'A'),sale(2,'B'),sale(3,phone=''),sale(4,phone='')],[],{},lambda r:None)
    assert len(c)==4
    assert not any(x['repeat_customer'] for x in c)


def test_billing_annotations_do_not_split_identity_but_branches_do():
    _,c=build([sale(1,'Business ( Payment every month )'),sale(2,'Business'),sale(3,'Business ( Shop 1 )')],[],{},lambda r:None)
    assert len(c)==2 and max(x['purchase_count'] for x in c)==2


def test_commercial_same_name_and_address_can_have_different_contacts():
    a=sale(1,'RESTAURANT CLIENT T');b=sale(2,'RESTAURANT CLIENT T ( Payment quarterly )',phone='0137654321')
    for r in (a,b):r.update(premise_type='COMMERCIAL',address_raw='12 Jalan Example, 40000 Selangor')
    _,customers=build([a,b],[],{},lambda r:None)
    assert len(customers)==1 and customers[0]['repeat_customer']
    assert customers[0]['identity_status']=='exact_name_and_address'


def test_counts_preserve_unknown_and_excluded_sales_without_private_fields():
    excluded=sale(3);excluded['include_in_sale_count']=False
    s,c=build([sale(1),sale(2,amount=None),excluded],[],{},lambda r:None)
    a=aggregate(s)
    assert a['coverage']['sales_rm']==100 and a['coverage']['sale_rows']==2
    assert a['sales'][0]['unknown_sale_values']==1
    assert all(not any(k in r for k in ('name','customer_key','sale_id','phone_raw')) for r in a['sales'])


def test_duplicate_grains_fail_closed():
    with pytest.raises(ValueError,match='Duplicate sale'): build([sale(1),sale(1)],[],{},lambda r:None)
    e=dict(calendar_name='A',event_id='x',event_date_local='2026-10-01')
    with pytest.raises(ValueError,match='Duplicate appointment'): build([],[e,e],{},lambda r:None)


def test_business_radius_uses_actual_grains_and_excludes_uncertain_edges():
    from webapp.business import radius
    s={'sales':[{'date':'2026-10-01','sales_rm':120,'location':{'latitude':3,'longitude':101,'uncertainty_km':.1}},
                {'date':'2026-10-01','sales_rm':50,'location':None},
                {'date':'2026-10-01','sales_rm':80,'location':{'latitude':3.04,'longitude':101,'uncertainty_km':2}}],
       'appointments':[{'date':'2026-10-02','location':{'latitude':3,'longitude':101,'uncertainty_km':.1}}]}
    r=radius(s,3,101,5)
    assert r['sales_rm']==120 and r['sale_rows']==1 and r['appointments']==1
    assert r['ambiguous_sales']==1 and r['unlocated_sales']==1
    assert radius(s,3,101,5,start='2026-10-02')['sale_rows']==0
    with pytest.raises(ValueError):radius(s,float('nan'),101,5)
