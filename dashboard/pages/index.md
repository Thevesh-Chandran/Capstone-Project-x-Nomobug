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

```sql months_all
select * from nomobug.sales_monthly where month < date_trunc('month', current_date) order by month
```

```sql sales_period
select * from ${months_all} where month between '${inputs.period.start}' and '${inputs.period.end}' order by month
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
select period_start, actual_bookings from nomobug.backtest
where period_start between '${inputs.period.start}' and '${inputs.period.end}' order by period_start
```

```sql top_areas
select regexp_replace(coalesce(nullif(split_part(district, ' / ', 2), ''), district), '^W\.P\. ', '') as area,
       sum(sales_rm) as sales_rm, sum(sales) as sales
from nomobug.sales_detail where district <> 'Unassigned' and month between '${inputs.period.start}' and '${inputs.period.end}'
group by 1 order by 2 desc limit 6
```

```sql pest_top
select pest as pest_group, sum(sales_rm) as sales_rm from nomobug.sales_detail
where pest <> 'Unspecified' and month between '${inputs.period.start}' and '${inputs.period.end}'
group by 1 order by 2 desc limit 6
```

```sql freshness
select max(extracted_at_utc) as latest from nomobug.freshness
```

<div class="hero">
  <h1>Management overview</h1>
  <span class="chip">Data as of <Value data={headline} column=as_of fmt="d mmm yyyy"/></span>
</div>




<div class="kpis">
  <BigValue data={sales_kpi2} value=last_12m_rm title="Sales, last 12 months" fmt='"RM"#,##0' comparison=vs_prior comparisonFmt=pct0 comparisonTitle="vs previous 12 months" sparkline=month sparklineType=bar sparklineColor="#4C55B8"/>
  <BigValue data={headline} value=bookings_next_2_weeks title="Bookings expected, next 2 weeks" fmt="#,##0"/>
  <BigValue data={headline} value=customers_to_call title="Customers needing closer attention"/>
  <BigValue data={headline} value=staff_hours_next_week title="Hours to plan, next week" fmt="#,##0"/>
</div>

## Staff workspace

<div class="row3">
  <div class="action">
    <div class="label">Service follow-up</div>
    {#if headline[0]?.customers_to_call > 0}
    <div class="big"><Value data={headline} column=customers_to_call fmt="#,##0"/> higher-risk services in the published snapshot</div>
    {:else}
    <div class="big">Check the current follow-up queue</div>
    {/if}
    <a class="go" data-to="returns" role="link" tabindex="0">Open service follow-up</a>
  </div>
  <div class="action green">
    <div class="label">Staffing</div>
    {#if headline[0]?.hours_to_keep_open > 0}
    <div class="big"><Value data={headline} column=hours_to_keep_open fmt="#,##0"/> hours to keep open in the published plan</div>
    {:else}
    <div class="big">Check current team capacity</div>
    {/if}
    <a class="go" data-to="plan" role="link" tabindex="0">Open staffing plan</a>
  </div>
  <div class="action amber">
    <div class="label">Bookings</div>
    <div class="big">Check the team calendars</div>
    <a class="go" data-to="bookings" role="link" tabindex="0">Open booking calendar</a>
  </div>
</div>

## Performance

<div class="card filters">
<DateRange name=period data={months_all} dates=month end={new Date()} defaultValue="Last 12 Months" title="Chart period · defaults to 12 completed months"/>
</div>

<div class="row2">
  <div class="card">
    <h3>Sales by month</h3>

    <BarChart data={sales_period} x=month y=sales_rm yFmt='"RM"#,##0' xFmt="mmm" colorPalette={['#5B63C9']} chartAreaHeight=220 labels=false/>
  </div>
  <div class="card">
    <h3>Bookings every 2 weeks</h3>

    <AreaChart data={backtest} x=period_start y=actual_bookings xFmt="d mmm" yMin=0 colorPalette={['#2E9CB8']} chartAreaHeight=220 fillOpacity=0.25/>
  </div>
</div>

<div class="row2">
  <div class="card">
    <h3>Top areas</h3>

    <DataTable data={top_areas} rowShading=false>
      <Column id=area title="Area"/>
      <Column id=sales_rm title="Sales" fmt='"RM"#,##0' contentType=bar barColor="#DCDDF4"/>
      <Column id=sales title="Purchases"/>
    </DataTable>
  </div>
  <div class="card">
    <h3>What customers buy</h3>

    <DataTable data={pest_top} rowShading=false>
      <Column id=pest_group title="Pest group"/>
      <Column id=sales_rm title="Sales" fmt='"RM"#,##0' contentType=bar barColor="#DCDDF4"/>
    </DataTable>
  </div>
</div>


<Details title="Definitions and coverage">

Hours to plan include the appointment-hour forecast plus an allowance equal to historical mean absolute error. This is a planning allowance, not a measured confidence interval.

Area totals cover records with a known district for the selected period.

</Details>
