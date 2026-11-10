---
title: Return visits and the model
sidebar_position: 6
---

```sql model_cmp
select regexp_replace(method, ' [(]chosen[)]', '') || case when chosen then ' (used)' else '' end as method,
       chosen, auc, ap, capture_10, capture_20, capture_30, precision_20
from nomobug.model_eval order by chosen desc, capture_20 desc
```

```sql model_kpi
select max(case when chosen then auc end) as auc,
       max(case when chosen then auc_low end) as auc_low, max(case when chosen then auc_high end) as auc_high,
       max(case when chosen then capture_20 end) as capture_20,
       max(case when chosen then precision_20 end) as precision_20,
       max(case when chosen then base_rate end) as base_rate,
       max(case when chosen then gain_vs_rule end) as gain,
       max(case when chosen then gain_vs_rule_low end) as gain_low, max(case when chosen then gain_vs_rule_high end) as gain_high,
       max(case when chosen then services end) as services, max(case when chosen then returns end) as returns,
       max(case when chosen then test_period end) as test_period,
       max(case when chosen then expected_returns end) as expected_returns, max(case when chosen then recorded_returns end) as recorded_returns
from nomobug.model_eval
```

```sql model_inp
select label as input, odds_multiplier, direction from nomobug.model_inputs order by abs(log_odds) desc
```

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
  <h1>Return visits and the model</h1>
</div>

<div class="card filters">
<DateRange name=sw_period data={sw_months} dates=month defaultValue="All Time" title="Period for the monthly charts"/>
<Dropdown name=sw_pest data={sw_pests} value=pest title="Pest (package fit and package mix)" multiple=true selectAllByDefault=true/>
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

    <DataTable data={difficulty} rowShading=false>
      <Column id=pest title="Pest mix" wrap=true/>
      <Column id=visits title="Visits" fmt="#,##0"/>
      <Column id=return_share title="Return share" fmt=pct0 contentType=bar barColor="#F3C5D1"/>
    </DataTable>
  </div>
  <div class="card">
    <h3>Package fit: return share</h3>

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


## How the return-visit model performs

<p class="note">Historical assessment on <Value data={model_kpi} column=services fmt="#,##0"/> later services (<Value data={model_kpi} column=test_period/>) held out from model fitting; <Value data={model_kpi} column=returns fmt="#,##0"/> of them had a recorded return visit.</p>

<div class="kpis">
  <BigValue data={model_kpi} value=capture_20 title="Returns reached by calling the top 20%" fmt=pct0/>
  <BigValue data={model_kpi} value=precision_20 title="Hit rate in the top 20%" fmt=pct0/>
  <BigValue data={model_kpi} value=base_rate title="Hit rate if called at random" fmt=pct0/>
  <BigValue data={model_kpi} value=auc title="Ranking score (AUC)" fmt="0.00"/>
</div>

<div class="card">
    <h3>The model against simpler options</h3>

    <DataTable data={model_cmp} rowShading=false>
      <Column id=method title="Method"/>
      <Column id=capture_10 title="Reached, top 10%" fmt=pct0/>
      <Column id=capture_20 title="Reached, top 20%" fmt=pct0 contentType=bar barColor="#DCDDF4"/>
      <Column id=capture_30 title="Reached, top 30%" fmt=pct0/>
      <Column id=precision_20 title="Hit rate, top 20%" fmt=pct0/>
      <Column id=auc title="AUC" fmt="0.00"/>
      <Column id=ap title="Avg precision" fmt="0.00"/>
    </DataTable>
</div>

<div class="card">
    <h3>What the model looks at</h3>

    <DataTable data={model_inp} rowShading=false rows=13>
      <Column id=input title="Input"/>
      <Column id=odds_multiplier title="Odds multiplier" fmt="0.00" contentType=colorscale colorScale={['#2E9CB8','#FFFFFF','#D9577A']} colorMid=1/>
      <Column id=direction title="Effect"/>
    </DataTable>
</div>

<Details title="What these numbers mean">

**Returns reached (capture).** If staff call the highest-scoring 20% of recent services, this is the share of all return visits that would be among those calls. The model reaches <Value data={model_kpi} column=capture_20 fmt=pct0/>; calling at random reaches about 20% by definition. Higher is better.

**Hit rate (precision).** Of the services in the top 20%, the share that really had a return visit: <Value data={model_kpi} column=precision_20 fmt=pct0/>, against <Value data={model_kpi} column=base_rate fmt=pct0/> for a random call. It shows how much less time is spent on calls that turn out fine.

**Gain over the simple rule.** The best simple rule (call every final service of a home programme) is the bar to beat. At the top 20% the model reaches <Value data={model_kpi} column=gain fmt=pct0/> more of the returns, with a likely range of <Value data={model_kpi} column=gain_low fmt=pct0/> to <Value data={model_kpi} column=gain_high fmt=pct0/> points.

**AUC (ranking score).** Pick one service that had a return visit and one that did not; AUC is how often the model scores the first one higher. 0.5 is a coin toss and 1.0 is perfect. The model scores <Value data={model_kpi} column=auc fmt="0.00"/> (likely range <Value data={model_kpi} column=auc_low fmt="0.00"/> to <Value data={model_kpi} column=auc_high fmt="0.00"/>).

**Average precision.** A single summary of the hit rate across every possible cut-off, useful when returns are rare. Random order scores about the return rate itself.

**Odds multiplier.** For an input that is yes or no, how many times the odds of a return visit change when it is yes, holding the other inputs fixed; for a number, per unit (per day, per doubling of price). It describes the records, not what causes pests to come back.

**Totals.** Across the test the model expected <Value data={model_kpi} column=expected_returns fmt="#,##0"/> return visits and <Value data={model_kpi} column=recorded_returns fmt="#,##0"/> were recorded, so use it to rank customers and keep a buffer when planning hours.

</Details>


<Details title="Historical assessment and the frozen future test">

These ranking results describe historical records. AUC measures ranking, not the percentage of correct yes/no predictions. Top-20% measures are comparison benchmarks, not a requirement to contact only some customers. Staff can continue following up with everyone.

The original frozen 30-day model has a separate prediction log and evaluation protocol. Its future result must include collection coverage, missed windows and complete outcome checks. Historical results here do not replace that test or repair missed predictions.

</Details>

<Details title="Definitions and coverage">

Observed patterns do not establish causes. Recorded return visits are not all verified warranty claims.

Share of visits that were return visits, pest mixes with 30+ visits

Pest × package, combinations with 15+ visits. Darker = more return visits.

Average rainfall in the 7 days before services, mm. Weather data runs to the last loaded month.

Same test services for every method. Reached = share of all return visits found by calling that share of services.

How much each input changes the odds of a return visit (1.0 = no change; above 1 raises it, below 1 lowers it)

</Details>
