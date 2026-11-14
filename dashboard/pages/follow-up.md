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
  <p>Estimated return risk within 30 days</p>

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

    <BarChart data={bands} x=chance_band y=services sort=false swapXY=true colorPalette={['#D9577A']} chartAreaHeight=200 labels=true yAxisLabels=false yGridlines=false yMax={Math.max(...bands.map(d => d.services ?? 0)) * 1.25}/>
  </div>
  <div class="card">
    <h3>Return visits actually recorded</h3>
<DateRange name=fu_period data={months_all} dates=month defaultValue="All Time" title="Period · this chart"/>

    <AreaChart data={service_monthly} x=month y=return_visits xFmt="mmm yy" colorPalette={['#D9577A']} chartAreaHeight=200 fillOpacity=0.25/>
  </div>
</div>
