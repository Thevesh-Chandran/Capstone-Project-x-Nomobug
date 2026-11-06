---
title: Service follow-up
sidebar_position: 2
---

```sql headline
select * from nomobug.headline
```

```sql call_list
select
  risk_rank, customer_name, service_date, call_from,
  chance_of_return, reason_1 as main_reason, suggested_action,
  cast(service_number as integer) || ' of ' || cast(programme_services as integer) as service, premise_type
from nomobug.call_list
where suggested_action like '${inputs.action}'
  and coalesce(premise_type, '') like '${inputs.premise.value}'
order by risk_rank
```

```sql premises
select distinct premise_type from nomobug.call_list where premise_type is not null order by 1
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
from nomobug.call_list group by 1, 2 order by band_order
```

```sql service_monthly
select * from nomobug.service_monthly order by month
```

<div class="hero">
  <h1>Who to call this week</h1>
  <p>Each recent service gets a chance of a pest-related return visit within 30 days. Call the highest first. These are model estimates for ranking calls, not confirmed problems.</p>
  <span class="chip">Record call results on the website's Service follow-up page</span>
</div>

<div class="kpis">
  <BigValue data={headline} value=customers_to_call title="Customers to call this week"/>
  <BigValue data={headline} value=expected_returns_open title="Expected return visits" fmt="#,##0"/>
  <BigValue data={headline} value=top_chance title="Highest chance" fmt=pct0/>
  <BigValue data={headline} value=services_open title="Recent services tracked"/>
</div>

<div class="card">
  <h3>Call list</h3>
  <p class="sub">Ranked by chance of a return visit. Filter by action or premise type.</p>

<ButtonGroup name=action>
  <ButtonGroupItem valueLabel="Call this week" value="Call this week" default/>
  <ButtonGroupItem valueLabel="Call if time allows" value="Call if time allows"/>
  <ButtonGroupItem valueLabel="Past the call window" value="Past the call window"/>
  <ButtonGroupItem valueLabel="All" value="%"/>
</ButtonGroup>

<Dropdown data={premises} name=premise value=premise_type title="Premise">
  <DropdownOption value="%" valueLabel="All premises"/>
</Dropdown>

<DataTable data={call_list} search=true rows=10 rowShading=false>
  <Column id=risk_rank title="#"/>
  <Column id=customer_name title="Customer"/>
  <Column id=service title="Service"/>
  <Column id=premise_type title="Premise"/>
  <Column id=service_date title="Serviced" fmt="d mmm"/>
  <Column id=chance_of_return title="Chance" fmt=pct0 contentType=bar barColor="#9DC3FA"/>
  <Column id=main_reason title="Why"/>
  <Column id=call_from title="Call from" fmt="d mmm"/>
</DataTable>
</div>

<div class="row2">
  <div class="card">
    <h3>Recent services by chance band</h3>
    <p class="sub">Most services are low risk; a few carry most of the expected returns</p>
    <BarChart data={bands} x=chance_band y=services sort=false colorPalette={['#2C6BE7']} chartAreaHeight=200 labels=true/>
  </div>
  <div class="card">
    <h3>Return visits actually recorded</h3>
    <p class="sub">Monthly warranty/return visits in the calendar</p>
    <AreaChart data={service_monthly} x=month y=return_visits xFmt="mmm yy" colorPalette={['#009778']} chartAreaHeight=200 fillOpacity=0.25/>
  </div>
</div>

<Details title="How reliable is this model?">
On past data (1,270 services, 108 recorded returns) the model ranked real return visits above other services 81% of the time (AUC 0.81). The top 20% of services held 62% of returns, against 21% if picked at random. Monthly totals ran about 17% low, so plan with a buffer. Full method: website → Prediction models.
</Details>
