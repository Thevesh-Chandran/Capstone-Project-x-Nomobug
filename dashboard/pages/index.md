---
title: Overview
sidebar_position: 1
---

```sql headline
select * from nomobug.headline
```

```sql sales_monthly
select * from nomobug.sales_monthly
where month >= date_trunc('month', current_date - interval 12 month)
  and month < date_trunc('month', current_date)
order by month
```

```sql sales_kpi
select
  sum(case when month >= date_trunc('month', current_date - interval 12 month) and month < date_trunc('month', current_date) then sales_rm end) as last_12m_rm,
  sum(case when month >= date_trunc('month', current_date - interval 24 month) and month < date_trunc('month', current_date - interval 12 month) then sales_rm end) as prior_12m_rm
from nomobug.sales_monthly
```

```sql sales_kpi2
select m.month, m.sales_rm, k.last_12m_rm, k.last_12m_rm / nullif(k.prior_12m_rm, 0) - 1 as vs_prior
from ${sales_monthly} m cross join ${sales_kpi} k
order by m.month
```

```sql backtest
select period_start, actual_bookings from nomobug.backtest order by period_start
```

```sql top_areas
select regexp_replace(coalesce(nullif(split_part(district, ' / ', 2), ''), district), '^W\.P\. ', '') as area,
       sales_rm, sales
from nomobug.area_sales order by sales_rm desc limit 6
```

```sql pest_top
select pest_group, sales_rm from nomobug.pest_groups order by sales_rm desc limit 6
```

```sql freshness
select max(extracted_at_utc) as latest from nomobug.freshness
```

<div class="hero">
  <h1>Management overview</h1>
  <p>Where the business stands, what the models expect, and what to do this week.</p>
  <span class="chip">Data as of <Value data={headline} column=as_of fmt="d mmm yyyy"/></span>
</div>

<div class="kpis">
  <BigValue data={sales_kpi2} value=last_12m_rm title="Sales, last 12 months" fmt='"RM"#,##0' comparison=vs_prior comparisonFmt=pct0 comparisonTitle="vs previous 12 months" sparkline=month sparklineType=bar sparklineColor="#2C6BE7"/>
  <BigValue data={headline} value=bookings_next_2_weeks title="Bookings expected, next 2 weeks" fmt="#,##0" link="/bookings"/>
  <BigValue data={headline} value=customers_to_call title="Customers to call this week" link="/follow-up"/>
  <BigValue data={headline} value=staff_hours_next_week title="Staff hours, next week" fmt="#,##0" link="/bookings"/>
</div>

## This week: what to do

<div class="row3">
  <div class="action">
    <div class="label">Service follow-up</div>
    <div class="big">Call <Value data={headline} column=customers_to_call/> customers</div>
    <p>Most likely to need a return visit. Top chance <Value data={headline} column=top_chance fmt=pct0/>.</p>
    <a href="/follow-up">Open the call list →</a>
  </div>
  <div class="action green">
    <div class="label">Staffing</div>
    <div class="big">Staff about <Value data={headline} column=staff_hours_next_week fmt="#,##0"/> hours</div>
    <p>Keep <Value data={headline} column=hours_to_keep_open fmt="#,##0"/> hours open for new bookings next week.</p>
    <a href="/bookings">See the staffing plan →</a>
  </div>
  <div class="action amber">
    <div class="label">Bookings</div>
    <div class="big">About <Value data={headline} column=bookings_next_2_weeks fmt="#,##0"/> bookings</div>
    <p>Expected in the next two weeks, likely <Value data={headline} column=bookings_likely_range/>.</p>
    <a href="/bookings">See the forecast →</a>
  </div>
</div>

## Performance

<div class="row2">
  <div class="card">
    <h3>Sales by month</h3>
    <p class="sub">Recorded package sales, last 12 full months</p>
    <BarChart data={sales_monthly} x=month y=sales_rm yFmt='"RM"#,##0' xFmt="mmm" colorPalette={['#2C6BE7']} chartAreaHeight=220 labels=false/>
  </div>
  <div class="card">
    <h3>Bookings per fortnight</h3>
    <p class="sub">Recorded two-week bookings, recent back-test windows</p>
    <AreaChart data={backtest} x=period_start y=actual_bookings xFmt="d mmm" colorPalette={['#009778']} chartAreaHeight=220 fillOpacity=0.25/>
  </div>
</div>

<div class="row2">
  <div class="card">
    <h3>Top areas</h3>
    <p class="sub">Sales in the last 12 months, areas with a known district</p>
    <DataTable data={top_areas} rowShading=false>
      <Column id=area title="Area"/>
      <Column id=sales_rm title="Sales" fmt='"RM"#,##0' contentType=bar barColor="#C3E0FD"/>
      <Column id=sales title="Purchases"/>
    </DataTable>
  </div>
  <div class="card">
    <h3>What customers buy</h3>
    <p class="sub">Sales by pest group, all recorded</p>
    <BarChart data={pest_top} x=pest_group y=sales_rm swapXY=true yFmt='"RM"#,##0' colorPalette={['#8B54D4']} chartAreaHeight=200/>
  </div>
</div>

<p class="note">Sales are recorded package prices, not cash received or profit. Model figures are estimates. Source data last extracted <Value data={freshness} column=latest fmt="d mmm yyyy h:mm"/> UTC.</p>
