"""Read-only staff review queue from recorded contract facts."""
from datetime import date,timedelta
import math

def review_queue(contracts,today):
    end=today+timedelta(days=6)
    counts={'upcoming':0,'missing':0,'unknown':0}
    tasks=[]
    for row in contracts:
        balance=row.get('sales_remaining_balance_rm')
        try:
            amount=float(balance)
            known=balance is not None and math.isfinite(amount)
        except (ValueError,TypeError):
            known=False;amount=0
        raw=row.get('next_scheduled_reminder_date')
        try: reminder=date.fromisoformat(str(raw)) if raw else None
        except ValueError: reminder=None
        if not known:
            kind='unknown';reason='Recorded balance unavailable';action='Check the Sales amount before deciding whether payment follow-up is needed.'
        elif amount<=0:continue
        elif reminder is None:
            kind='missing';reason='Balance recorded; reminder date missing';action='Check the contract and confirm the reminder schedule with staff.'
        elif today<=reminder<=end:
            kind='upcoming';reason='Source reminder date within 7 days';action='Check the latest Sales balance; contact the customer if still appropriate.'
        else:continue
        counts[kind]+=1
        tasks.append({**row,'review_kind':kind,'review_reason':reason,'review_action':action})
    tasks.sort(key=lambda r:({'upcoming':0,'unknown':1,'missing':2}[r['review_kind']],str(r.get('next_scheduled_reminder_date') or ''),r.get('name','')))
    return {'as_of':today.isoformat(),'through':end.isoformat(),'counts':counts,'tasks':tasks,
        'notice':'Review suggestions only. A reminder date does not prove nonpayment, an overdue instalment or a sent message. No reminders are sent by this system.'}
