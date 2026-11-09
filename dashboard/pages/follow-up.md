---
title: Service follow-up
sidebar_position: 2
---

```sql model_eval
select
  max(case when chosen then services end) as services,
  max(case when chosen then returns end) as returns,
  max(case when chosen then test_period end) as test_period,
  max(case when chosen then auc end) as auc,
  max(case when chosen then capture_20 end) as capture_score,
  max(case when method like 'Rule%' then capture_20 end) as capture_rule,
  max(case when method like 'Random%' then capture_20 end) as capture_random,
  1 - max(case when chosen then expected_returns / nullif(recorded_returns, 0) end) as undercount
from nomobug.model_eval
```

```sql headline
select * from nomobug.headline
```

```sql bands
select case
    when chance_of_return >= 0.2 then '20% or more'
    when chance_of_return >= 0.1 then '10–20%'
    when chance_of_return >= 0.05 then '5–10%'
    else 'Under 5%' end as chance_band,
  case
    when chance_of_return >= 0.2 then 1 when chance_of_return >= 0.1 then 2
    when chance_of_return >= 0.05 then 3 else 4 end as band_order,
  count(*) as services
from nomobug.risk_scores where coalesce(premise_type, 'Unknown') in ${inputs.fu_premise.value} group by 1, 2 order by band_order
```

```sql fu_premises
select distinct coalesce(premise_type, 'Unknown') as premise from nomobug.risk_scores order by 1
```

```sql months_all
select * from nomobug.service_monthly where month < date_trunc('month', current_date) order by month
```

```sql service_monthly
select * from ${months_all} where month between '${inputs.fu_period.start}' and '${inputs.fu_period.end}' order by month
```

<div class="hero">
  <h1>Customers needing closer attention</h1>
  <p>Each recent service gets a chance of a pest-related return visit within 30 days. Use the estimates to prepare closer checks alongside routine follow-up. These are model estimates for ranking calls, not confirmed problems.</p>
  <span class="chip">The call list and call results are below</span>
</div>




<div class="card">
<h3>Predicting a recorded return within 30 days</h3>
<p>Historical assessment · <Value data={model_eval} column=test_period/> · <Value data={model_eval} column=services fmt="#,##0"/> services · <Value data={model_eval} column=returns/> returns</p>
<p>Ranking AUC <Value data={model_eval} column=auc fmt="0.00"/> · 0.5 represents random ranking and 1.0 perfect ranking. Future evaluation is pending.</p>
</div>

<div class="kpis">
  <BigValue data={headline} value=customers_to_call title="Customers needing closer attention"/>
  <BigValue data={headline} value=expected_returns_open title="Expected return visits" fmt="#,##0"/>
  <BigValue data={headline} value=top_chance title="Highest chance" fmt=pct0/>
  <BigValue data={headline} value=services_open title="Recent services tracked"/>
</div>


<div class="row2">
  <div class="card">
    <h3>Recent services by chance band</h3>
<Dropdown name=fu_premise data={fu_premises} value=premise title="Premise · this chart" multiple=true selectAllByDefault=true/>
    <p class="sub">Most services are low risk; a few carry most of the expected returns</p>
    <BarChart data={bands} x=chance_band y=services sort=false swapXY=true colorPalette={['#D9577A']} chartAreaHeight=200 labels=true yAxisLabels=false yGridlines=false yMax={Math.max(...bands.map(d => d.services ?? 0)) * 1.25}/>
  </div>
  <div class="card">
    <h3>Return visits actually recorded</h3>
<DateRange name=fu_period data={months_all} dates=month defaultValue="All Time" title="Period · this chart"/>
    <p class="sub">Monthly warranty/return visits in the calendar, full months only</p>
    <AreaChart data={service_monthly} x=month y=return_visits xFmt="mmm yy" colorPalette={['#D9577A']} chartAreaHeight=200 fillOpacity=0.25/>
  </div>
</div>

<Details title="How reliable is this model?">
Historical assessment on <Value data={model_eval} column=services fmt="#,##0"/> later services (<Value data={model_eval} column=test_period/>) with <Value data={model_eval} column=returns fmt="#,##0"/> recorded return visits, the model ranked real return visits above other services <Value data={model_eval} column=auc fmt=pct0/> of the time. Calling the top 20% of services reaches <Value data={model_eval} column=capture_score fmt=pct0/> of returns, against <Value data={model_eval} column=capture_rule fmt=pct0/> for the best simple rule and <Value data={model_eval} column=capture_random fmt=pct0/> picked at random. Its totals ran <Value data={model_eval} column=undercount fmt=pct0/> low, so plan with a buffer. Full method: Return visits & models page.
</Details>

<Details title="Historical assessment and the frozen future test">

These ranking results describe historical records. AUC measures ranking, not the percentage of correct yes/no predictions. Top-20% measures are comparison benchmarks, not a requirement to contact only some customers. Staff can continue following up with everyone.

The original frozen 30-day model has a separate prediction log and evaluation protocol. Its future result must include collection coverage, missed windows and complete outcome checks. Historical results here do not replace that test or repair missed predictions.

</Details>
