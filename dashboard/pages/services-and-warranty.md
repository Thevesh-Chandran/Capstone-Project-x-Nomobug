---
title: Services & warranty
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

```sql fit
with f as (
  select
    case when lower(pest_type) like '%anai%' then 'Termite'
         when lower(pest_type) like '%tikus%' and lower(pest_type) like '%lipas%' then 'Cockroach + rodent'
         when lower(pest_type) like '%semut%' and lower(pest_type) like '%lipas%' then 'Cockroach + ant'
         when lower(pest_type) like '%lipas%' then 'Cockroach'
         when lower(pest_type) like '%tikus%' then 'Rodent'
         when lower(pest_type) like '%semut%' then 'Ant'
         else 'Other' end as pest,
    case when upper(package_type) like 'B2B%' then 'Business ' else 'Home ' end
      || coalesce(nullif(regexp_extract(package_type, '([0-9]+) *[xX]', 1), '') || 'x', 'other') as package,
    packages, visits, return_share * visits as returns, sales_rm
  from nomobug.package_fit
)
select pest, package, sum(packages) as packages, sum(sales_rm) as sales_rm,
       sum(returns) / nullif(sum(visits), 0) as return_share
from f group by 1, 2 having sum(visits) >= 15 order by packages desc
```

```sql weather
select month,
  max(case when event_group = 'recorded_warranty_signal' then events end) as return_visits,
  max(case when event_group = 'other_scheduled_service_entry' then events end) as other_visits,
  max(case when event_group = 'other_scheduled_service_entry' then rain_7d_mm end) as rain_7d_mm,
  max(case when event_group = 'other_scheduled_service_entry' then humidity_7d end) as humidity_7d
from nomobug.weather_monthly group by 1 order by 1
```

```sql weather2
select *, return_visits / nullif(return_visits + other_visits, 0) as return_share from ${weather}
```

```sql reasons
select month,
  case reason when 'post_package_sequence' then 'Visit after the programme ended'
              when 'explicit_warranty_label' then 'Labelled warranty visit'
              when 'manual_review_confirmed_claim' then 'Confirmed claim (owner review)'
              else reason end as reason,
  returns
from nomobug.recurrence order by month
```

```sql kpi
select sum(return_visits) as returns, sum(visits) as visits, sum(return_visits) / nullif(sum(visits), 0) as share,
       (select pest from ${difficulty} where visits >= 100 order by return_share desc limit 1) as hardest
from ${difficulty}
```

<div class="hero">
  <h1>Services & warranty</h1>
  <p>Which treatments lead to more return visits, how packages compare, and whether rainfall moves with returns. These are observed patterns, not causes.</p>
  <span class="chip">Return visits = calendar entries for warranty or follow-up visits</span>
</div>

<div class="kpis">
  <BigValue data={kpi} value=visits title="Service visits analysed" fmt="#,##0"/>
  <BigValue data={kpi} value=returns title="Return visits" fmt="#,##0"/>
  <BigValue data={kpi} value=share title="Return-visit share" fmt=pct1/>
  <BigValue data={kpi} value=hardest title="Hardest pest mix (100+ visits)"/>
</div>

<div class="row2">
  <div class="card">
    <h3>Treatment difficulty by pest</h3>
    <p class="sub">Share of visits that were return visits, pest mixes with 30+ visits</p>
    <BarChart data={difficulty} x=pest y=return_share swapXY=true yFmt=pct0 colorPalette={['#E24A3F']} chartAreaHeight=260 labels=true/>
  </div>
  <div class="card">
    <h3>Package fit: return share</h3>
    <p class="sub">Pest × package, combinations with 15+ visits. Darker = more return visits.</p>
    <Heatmap data={fit} x=package y=pest value=return_share valueFmt=pct0 colorScale={['#F3F7FA','#E78C08','#E24A3F']} valueLabels=true chartAreaHeight=260/>
  </div>
</div>

<div class="card">
  <h3>Rainfall and return visits</h3>
  <p class="sub">Monthly return-visit share (bars) and average rainfall in the 7 days before services (line)</p>
  <BarChart data={weather2} x=month y=return_share yFmt=pct0 y2=rain_7d_mm y2SeriesType=line y2Fmt='#,##0.0" mm"' xFmt="mmm yy" colorPalette={['#2C6BE7','#009778']} chartAreaHeight=240/>
</div>

<div class="row2">
  <div class="card">
    <h3>Why visits counted as returns</h3>
    <p class="sub">Return visits by month and how they were identified</p>
    <BarChart data={reasons} x=month y=returns series=reason type=stacked xFmt="mmm yy" chartAreaHeight=240/>
  </div>
  <div class="card">
    <h3>Package mix</h3>
    <p class="sub">Packages sold by pest and package type</p>
    <DataTable data={fit} rows=10 rowShading=false>
      <Column id=pest title="Pest"/>
      <Column id=package title="Package"/>
      <Column id=packages title="Packages"/>
      <Column id=sales_rm title="Sales" fmt='"RM"#,##0'/>
      <Column id=return_share title="Return share" fmt=pct0 contentType=colorscale colorScale={['#FFFFFF','#E24A3F']}/>
    </DataTable>
  </div>
</div>

<p class="note">Weather is matched to each service's location and shows association only; rain does not prove a treatment failed. Small groups are hidden to avoid misleading percentages.</p>
