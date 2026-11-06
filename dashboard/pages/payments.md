---
title: Payments
sidebar_position: 5
---

```sql reminders
select * from nomobug.reminders order by reminder_date
```

```sql due
select
  coalesce(sum(case when reminder_date between current_date and current_date + interval 7 day then reminders end), 0) as due_7,
  coalesce(sum(case when reminder_date between current_date and current_date + interval 30 day then reminders end), 0) as due_30,
  coalesce(sum(case when reminder_date between current_date and current_date + interval 90 day then reminders end), 0) as due_90,
  count(distinct billing_arrangement) as arrangements
from nomobug.reminders
```

```sql upcoming
select reminder_date, billing_arrangement, reminders,
       date_diff('day', current_date, reminder_date) as days_away
from nomobug.reminders
where reminder_date >= current_date
order by reminder_date
limit 40
```

```sql by_month
select date_trunc('month', reminder_date) as month, billing_arrangement, sum(reminders) as reminders
from nomobug.reminders
where reminder_date >= current_date - interval 3 month and reminder_date < current_date + interval 6 month
group by 1, 2 order by 1
```

```sql by_arrangement
select billing_arrangement, sum(reminders) as reminders
from nomobug.reminders where reminder_date >= current_date
group by 1 order by 2 desc
```

<div class="hero">
  <h1>Payment reminders</h1>
  <p>The owner's schedule for contacting clients on recurring contracts. A reminder date does not show that a payment was received or that a reminder was sent.</p>
  <span class="chip">From the Sales sheet reminder schedule</span>
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
    <BarChart data={by_arrangement} x=billing_arrangement y=reminders swapXY=true colorPalette={['#2C6BE7']} chartAreaHeight=240 labels=true/>
  </div>
</div>

<div class="card">
  <h3>Upcoming reminders</h3>
  <p class="sub">Next dates first</p>
  <DataTable data={upcoming} rows=10 rowShading=false>
    <Column id=reminder_date title="Reminder date" fmt="ddd d mmm yyyy"/>
    <Column id=days_away title="Days away" contentType=colorscale colorScale={['#2C6BE7','#E3F3FF']}/>
    <Column id=billing_arrangement title="Arrangement"/>
    <Column id=reminders title="Reminders"/>
  </DataTable>
</div>
