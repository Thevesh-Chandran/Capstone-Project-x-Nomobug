---
title: Service follow-up
sidebar_position: 2
---

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
from nomobug.risk_scores group by 1, 2 order by band_order
```

```sql service_monthly
select * from nomobug.service_monthly where month < date_trunc('month', current_date) order by month
```

<div class="hero">
  <h1>Who to call this week</h1>
  <p>Each recent service gets a chance of a pest-related return visit within 30 days. Call the highest first. These are model estimates for ranking calls, not confirmed problems.</p>
  <span class="chip">The call list and call results are below</span>
</div>

<div class="kpis">
  <BigValue data={headline} value=customers_to_call title="Customers to call this week"/>
  <BigValue data={headline} value=expected_returns_open title="Expected return visits" fmt="#,##0"/>
  <BigValue data={headline} value=top_chance title="Highest chance" fmt=pct0/>
  <BigValue data={headline} value=services_open title="Recent services tracked"/>
</div>


<div class="row2">
  <div class="card">
    <h3>Recent services by chance band</h3>
    <p class="sub">Most services are low risk; a few carry most of the expected returns</p>
    <BarChart data={bands} x=chance_band y=services sort=false swapXY=true colorPalette={['#D9577A']} chartAreaHeight=200 labels=true yAxisLabels=false yGridlines=false yMax={Math.max(...bands.map(d => d.services ?? 0)) * 1.25}/>
  </div>
  <div class="card">
    <h3>Return visits actually recorded</h3>
    <p class="sub">Monthly warranty/return visits in the calendar, full months only</p>
    <AreaChart data={service_monthly} x=month y=return_visits xFmt="mmm yy" colorPalette={['#D9577A']} chartAreaHeight=200 fillOpacity=0.25/>
  </div>
</div>

<Details title="How reliable is this model?">
On past data (1,270 services, 108 recorded returns) the model ranked real return visits above other services 81% of the time (AUC 0.81). The top 20% of services held 62% of returns, against 21% if picked at random. Monthly totals ran about 17% low, so plan with a buffer. Full method: Return visits & models page.
</Details>
