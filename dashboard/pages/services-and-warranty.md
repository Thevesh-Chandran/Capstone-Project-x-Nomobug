---
title: Return visits
sidebar_position: 6
---

```sql difficulty
with d as (
  select
    array_to_string(list_filter([
      case when lower(pest_type) like '%lipas%' or lower(pest_type) like '%cockroach%' then 'Cockroach' end,
      case when lower(pest_type) like '%semut%' or lower(pest_type) like '%ant%' and lower(pest_type) not like '%anai%' then 'Ant' end,
      case when lower(pest_type) like '%tikus%' or lower(pest_type) like '%rat%' or lower(pest_type) like '%rodent%' then 'Rodent' end,
      case when lower(pest_type) like '%anai%' or lower(pest_type) like '%termite%' then 'Termite' end,
      case when lower(pest_type) like '%nyamuk%' or lower(pest_type) like '%mosquito%' then 'Mosquito' end
    ], x -> x is not null), ' + ') as pest,
    visits, return_visits
  from nomobug.difficulty
)
select coalesce(nullif(pest, ''), 'Other') as pest, sum(visits) as visits, sum(return_visits) as return_visits,
       sum(return_visits) / nullif(sum(visits), 0) as return_share
from d group by 1 having sum(visits) >= 30 order by visits desc
```

```sql sw_months
select distinct month from nomobug.recurrence where month < date_trunc('month', current_date) order by 1
```

```sql fit_all
with f as (
  select
    case when lower(pest_type) like '%anai%' then 'Termite'
         when lower(pest_type) like '%tikus%' and lower(pest_type) like '%lipas%' then 'Cockroach + rodent'
         when lower(pest_type) like '%semut%' and lower(pest_type) like '%lipas%' then 'Cockroach + ant'
         when lower(pest_type) like '%lipas%' then 'Cockroach'
         when lower(pest_type) like '%tikus%' then 'Rodent'
         when lower(pest_type) like '%semut%' then 'Ant'
         else 'Other' end as pest,
    case when upper(package_type) like 'B2B%' then 'B2B ' else 'Home ' end
      || coalesce(nullif(regexp_extract(package_type, '([0-9]+) *[xX]', 1), '') || 'x', 'misc') as package,
    packages, visits, return_share * visits as returns, sales_rm
  from nomobug.package_fit
)
select pest, package, sum(packages) as packages, sum(sales_rm) as sales_rm,
       sum(returns) / nullif(sum(visits), 0) as return_share
from f where package in (select package from f group by 1 having sum(visits) >= 60)
group by 1, 2 having sum(visits) >= 15 order by packages desc
```

```sql sw_pests
select distinct pest from ${fit_all} order by 1
```

```sql fit
select * from ${fit_all} where pest in ${inputs.sw_pest.value} order by packages desc
```

```sql weather
select month,
  max(case when event_group = 'recorded_warranty_signal' then events end) as return_visits,
  max(case when event_group = 'other_scheduled_service_entry' then events end) as other_visits,
  max(case when event_group = 'other_scheduled_service_entry' then rain_7d_mm end) as rain_7d_mm,
  max(case when event_group = 'other_scheduled_service_entry' then humidity_7d end) as humidity_7d
from nomobug.weather_monthly where month < date_trunc('month', current_date)
  and month between '${inputs.sw_period.start}' and '${inputs.sw_period.end}' group by 1 order by 1
```

```sql weather2
select month, return_visits / nullif(return_visits + other_visits, 0) as "Return-visit share", rain_7d_mm as "Rain before visits (mm)" from ${weather}
```

```sql reasons
select month,
  case reason when 'post_package_sequence' then 'After programme'
              when 'explicit_warranty_label' then 'Labelled warranty'
              when 'manual_review_confirmed_claim' then 'Owner-confirmed'
              else reason end as reason,
  returns
from nomobug.recurrence where month < date_trunc('month', current_date)
  and month between '${inputs.sw_period.start}' and '${inputs.sw_period.end}' order by month
```

```sql kpi
select sum(return_visits) as returns, sum(visits) as visits, sum(return_visits) / nullif(sum(visits), 0) as share,
       (select pest from ${difficulty} where visits >= 100 order by return_share desc limit 1) as hardest
from ${difficulty}
```

<div class="hero">
  <h1>Return visits</h1>
</div>

<div class="card filters">
<DateRange name=sw_period data={sw_months} dates=month defaultValue="All Time" title="Period for the monthly charts"/>
<Dropdown name=sw_pest data={sw_pests} value=pest title="Pest (package fit and package mix)" multiple=true selectAllByDefault=true/>
</div>


<div class="kpis">
  <BigValue data={kpi} value=visits title="Service visits analysed" fmt="#,##0"/>
  <BigValue data={kpi} value=returns title="Return visits" fmt="#,##0"/>
  <BigValue data={kpi} value=share title="Return-visit share" fmt=pct1/>
  <BigValue data={kpi} value=hardest title="Highest return share (100+ visits)"/>
</div>

<div class="row2">
  <div class="card">
    <h3>Recorded returns by pest</h3>

    <DataTable data={difficulty} rowShading=false>
      <Column id=pest title="Pest mix" wrap=true/>
      <Column id=visits title="Visits" fmt="#,##0"/>
      <Column id=return_share title="Return share" fmt=pct0 contentType=bar barColor="#F3C5D1"/>
    </DataTable>
  </div>
  <div class="card">
    <h3>Return share by pest and package</h3>

    <Heatmap data={fit} x=package y=pest value=return_share valueFmt=pct0 colorScale={['#FBEFF2','#D9577A']} valueLabels=true chartAreaHeight=260/>
  </div>
</div>

<div class="row2">
  <div class="card">
    <h3>Return-visit share by month</h3>

    <BarChart data={weather2} x=month y="Return-visit share" yFmt=pct0 xFmt="mmm yy" colorPalette={['#D9577A']} chartAreaHeight=220/>
  </div>
  <div class="card">
    <h3>Rain before visits</h3>

    <LineChart data={weather2} x=month y="Rain before visits (mm)" yFmt='#,##0.0' xFmt="mmm yy" colorPalette={['#2E9CB8']} chartAreaHeight=220 markers=true/>
  </div>
</div>

<div class="row2">
  <div class="card">
    <h3>Why visits counted as returns</h3>

    <BarChart data={reasons} x=month y=returns series=reason type=stacked xFmt="mmm yy" chartAreaHeight=240/>
  </div>
  <div class="card">
    <h3>Package mix</h3>

    <DataTable data={fit} rows=10 rowShading=false>
      <Column id=pest title="Pest"/>
      <Column id=package title="Package"/>
      <Column id=packages title="Packages"/>
      <Column id=return_share title="Return share" fmt=pct0 contentType=colorscale colorScale={['#FFFFFF','#D9577A']}/>
    </DataTable>
  </div>
</div>


<Details title="Definitions and coverage">

Observed patterns do not establish causes. Recorded return visits are not all verified warranty claims.

Share of visits that were return visits, pest mixes with 30+ visits

Pest × package, combinations with 15+ visits. Darker = more return visits.

Average rainfall in the 7 days before services, mm. Weather data runs to the last loaded month.

Same test services for every method. Reached = share of all return visits found by calling that share of services.

How much each input changes the odds of a return visit (1.0 = no change; above 1 raises it, below 1 lowers it)

</Details>
