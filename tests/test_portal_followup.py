from datetime import date
from webapp.followup import review_queue

def test_review_queue_uses_dates_not_payment_status():
    rows=[{'name':'Upcoming','sales_remaining_balance_rm':50,'next_scheduled_reminder_date':'2026-10-23'}, {'name':'Past','sales_remaining_balance_rm':50,'next_scheduled_reminder_date':'2026-10-16'}, {'name':'Future','sales_remaining_balance_rm':50,'next_scheduled_reminder_date':'2026-10-24'}, {'name':'Settled','sales_remaining_balance_rm':0,'next_scheduled_reminder_date':'2026-10-17'}]
    q=review_queue(rows,date(2026,10,17))
    assert [r['name'] for r in q['tasks']]==['Upcoming']
    assert q['counts']=={'upcoming':1,'missing':0,'unknown':0}
    assert 'overdue' not in q['tasks'][0]['review_reason']

def test_review_queue_preserves_unknown_balances_and_invalid_dates():
    q=review_queue([{'name':'Unknown','sales_remaining_balance_rm':None},{'name':'Invalid','sales_remaining_balance_rm':50,'next_scheduled_reminder_date':'PENDING'},{'name':'Missing','sales_remaining_balance_rm':50},{'name':'Bad amount','sales_remaining_balance_rm':'#VALUE!'}],date(2026,10,17))
    assert q['counts']=={'upcoming':0,'missing':2,'unknown':2}
    assert len(q['tasks'])==4

def test_review_queue_does_not_mutate_records():
    rows=[{'name':'A','sales_remaining_balance_rm':10}]
    review_queue(rows,date(2026,10,17))
    assert 'review_reason' not in rows[0]
