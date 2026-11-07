---
title: Payments
sidebar_position: 7
---

```sql balances_all
select * from nomobug.contract_balances order by remaining_rm desc
```

```sql billing_list
select billing from ${balances_all}
```

```sql balances
select * from ${balances_all} where billing in ${inputs.billing.value}
```

```sql balance_kpi
select sum(contract_value_rm) as value_rm, sum(paid_rm) as paid_rm, sum(remaining_rm) as remaining_rm,
  sum(contracts) as contracts, sum(contracts_with_balance) as with_balance,
  sum(paid_rm) / nullif(sum(contract_value_rm), 0) as paid_share
from ${balances}
```

```sql balance_long
select billing, 'Recorded as paid' as status, 1 as o, paid_rm as rm from ${balances}
union all select billing, 'Still to collect', 2, remaining_rm from ${balances}
order by o
```

```sql reminders_all
select * from nomobug.reminders order by reminder_date
```

```sql arrangements
select distinct billing_arrangement from ${reminders_all} order by 1
```

```sql reminders
select * from ${reminders_all} where billing_arrangement in ${inputs.pay_arr.value} order by reminder_date
```

```sql due
select
  coalesce(sum(case when reminder_date between current_date and current_date + interval 7 day then reminders end), 0) as due_7,
  coalesce(sum(case when reminder_date between current_date and current_date + interval 30 day then reminders end), 0) as due_30,
  coalesce(sum(case when reminder_date between current_date and current_date + interval 90 day then reminders end), 0) as due_90,
  count(distinct billing_arrangement) as arrangements
from ${reminders}
```

```sql upcoming
select reminder_date, upper(substr(billing_arrangement,1,1)) || lower(substr(billing_arrangement,2)) as billing_arrangement, reminders,
       date_diff('day', current_date, reminder_date) as days_away
from ${reminders}
where reminder_date >= current_date
order by reminder_date
limit 40
```

```sql by_month
select date_trunc('month', reminder_date) as month, billing_arrangement, sum(reminders) as reminders
from ${reminders}
where reminder_date >= current_date - interval 3 month and reminder_date < current_date + interval 6 month
group by 1, 2 order by 1
```

```sql by_arrangement
select billing_arrangement, sum(reminders) as reminders
from ${reminders} where reminder_date >= current_date
group by 1 order by 2 desc
```

<div class="hero">
  <h1>Payment reminders</h1>
  <p>The owner's schedule for contacting clients on recurring contracts. A reminder date does not show that a payment was received or that a reminder was sent.</p>
  <span class="chip">From the Sales sheet reminder schedule</span>
</div>

## Recurring contracts: still to collect

<div class="card">
<Dropdown name=billing data={billing_list} value=billing title="Billing arrangement" multiple=true selectAllByDefault=true/>
</div>

<div class="kpis">
  <BigValue data={balance_kpi} value=remaining_rm title="Still to collect" fmt='"RM"#,##0'/>
  <BigValue data={balance_kpi} value=paid_rm title="Recorded as paid" fmt='"RM"#,##0'/>
  <BigValue data={balance_kpi} value=paid_share title="Share of contract value paid" fmt=pct0/>
  <BigValue data={balance_kpi} value=with_balance title="Contracts with a balance"/>
</div>

<div class="row2">
  <div class="card">
    <h3>Paid vs still to collect</h3>
    <p class="sub">Recurring contracts by billing arrangement</p>
    <BarChart data={balance_long} x=billing y=rm series=status type=stacked swapXY=true yFmt='"RM"#,##0' seriesOrder={['Recorded as paid','Still to collect']} colorPalette={['#3FA27A','#D97E45']} chartAreaHeight=220/>
  </div>
  <div class="card">
    <h3>Contract balances</h3>
    <p class="sub">From recorded Sales amounts; confirm with the client record before chasing</p>
    <DataTable data={balances} rowShading=false>
      <Column id=billing title="Billing"/>
      <Column id=contracts title="Contracts"/>
      <Column id=paid_rm title="Paid" fmt='"RM"#,##0'/>
      <Column id=remaining_rm title="To collect" fmt='"RM"#,##0' contentType=bar barColor="#F4D9C6"/>
    </DataTable>
  </div>
</div>

## Reminder schedule

<div class="card filters">
<Dropdown name=pay_arr data={arrangements} value=billing_arrangement title="Billing arrangement" multiple=true selectAllByDefault=true/>
</div>

<div class="kpis">
  <BigValue data={due} value=due_7 title="Due in the next 7 days"/>
  <BigValue data={due} value=due_30 title="Due in the next 30 days"/>
  <BigValue data={due} value=due_90 title="Due in the next 90 days"/>
  <BigValue data={due} value=arrangements title="Billing arrangements"/>
</div>

<div class="row2">
  <div class="card">
    <h3>Reminders by month</h3>
    <p class="sub">Three months back to six months ahead</p>
    <BarChart data={by_month} x=month y=reminders series=billing_arrangement type=stacked xFmt="mmm yy" chartAreaHeight=240/>
  </div>
  <div class="card">
    <h3>Upcoming by arrangement</h3>
    <p class="sub">All future reminder dates</p>
    <BarChart data={by_arrangement} x=billing_arrangement y=reminders swapXY=true colorPalette={['#B8901A']} chartAreaHeight=240 labels=true yAxisLabels=false yGridlines=false yMax={Math.max(...by_arrangement.map(d => d.reminders ?? 0)) * 1.25}/>
  </div>
</div>



## Recorded refunds

```sql refund_summary
select * from nomobug.refunds
```
<div class="card">
<p class="sub">All recorded refund entries, separate from contract balances above. A completed annotation is not proof of bank settlement. Missing dates remain in the table.</p>
<DataTable data={refund_summary}>
<Column id=refund_period title="Refund month"/>
<Column id=refund_source_rows title="Entries"/>
<Column id=recorded_refund_amount_rm title="Recorded amount" fmt='"RM"#,##0.00'/>
<Column id=recorded_complete_rows title="Marked complete"/>
<Column id=status_review_rows title="Status to check"/>
<Column id=amount_review_rows title="Amounts to check"/>
<Column id=date_review_rows title="Dates to check"/>
</DataTable>
</div>
