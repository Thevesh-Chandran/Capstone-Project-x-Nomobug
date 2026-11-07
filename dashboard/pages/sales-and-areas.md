---
title: Sales & customers
sidebar_position: 4
---

```sql detail
select *,
  regexp_replace(coalesce(nullif(split_part(district, ' / ', 2), ''), district), '^W\.P\. ', '') as area,
  case when package ilike 'B2B%' then 'Business ' || coalesce(nullif(regexp_extract(package, '([0-9]+) *[xX]', 1), '') || 'x', 'other')
       when package ilike 'GPC%' then 'Home ' || coalesce(nullif(regexp_extract(package, '([0-9]+) *[xX]', 1), '') || 'x', 'other')
       else package end as package_group
from nomobug.sales_detail
```

```sql facts
select * replace (case when billing ilike 'de%sit' or billing ilike 'deposit%' then 'Deposit'
                       when billing in ('Op','Gp') or billing is null or billing = '' then 'Other'
                       else billing end as billing),
  case when package ilike 'B2B%' then 'Business ' || coalesce(nullif(regexp_extract(package, '([0-9]+) *[xX]', 1), '') || 'x', 'other')
       when package ilike 'GPC%' then 'Home ' || coalesce(nullif(regexp_extract(package, '([0-9]+) *[xX]', 1), '') || 'x', 'other')
       else package end as package_group
from nomobug.sales_facts
```

```sql premises
select distinct premise from ${detail} order by 1
```

```sql areas_list
select area, sum(sales_rm) from ${detail} where area <> 'Unassigned' group by 1 order by 2 desc
```

```sql packages_list
select package_group, sum(sales) from ${detail} group by 1 order by 2 desc
```

```sql f
select * from ${detail}
where month between '${inputs.period.start}' and '${inputs.period.end}'
  and premise in ${inputs.premise.value}
  and package_group in ${inputs.package.value}
  and (area in ${inputs.area.value} or '${inputs.area_mode}' = 'all')
```

```sql ff
select * from ${facts}
where closed_date between '${inputs.period.start}' and '${inputs.period.end}'
  and premise in ${inputs.premise.value}
  and package_group in ${inputs.package.value}
  and client_type like '${inputs.client}'
```

```sql kpi
select sum(sales_rm) as sales_rm, sum(sales) as sales, sum(sales_rm) / nullif(sum(sales), 0) as avg_sale,
  sum(case when premise = 'Residential' then sales_rm end) / nullif(sum(sales_rm), 0) as residential_share
from ${f}
```

```sql trend
select date_trunc('month', month) as month, premise, sum(sales_rm) as sales_rm from ${f} group by 1, 2 order by 1
```

```sql by_premise
select premise, sum(sales_rm) as sales_rm, sum(sales) as sales from ${f} group by 1 order by 2 desc
```

```sql by_area
select area, sum(sales_rm) as sales_rm, sum(sales) as sales from ${f} where area <> 'Unassigned' group by 1 order by 2 desc limit 12
```

```sql top_packages
select package_group as package, sum(sales) as sales, sum(sales_rm) as sales_rm, sum(sales_rm) / nullif(sum(sales), 0) as avg_rm
from ${f} where package_group <> 'Unspecified' group by 1 order by 3 desc limit 10
```

```sql pests
select pest, sum(sales_rm) as sales_rm from ${f} where pest <> 'Unspecified' group by 1 order by 2 desc limit 8
```

```sql client_mix
select client_type, count(*) as sales, sum(sale_total_rm) as sales_rm, avg(sale_total_rm) as avg_rm from ${ff} group by 1 order by 2 desc
```

```sql billing_mix
select billing, count(*) as sales, sum(sale_total_rm) as sales_rm from ${ff} group by 1 order by 2 desc
```

```sql salespeople
select salesperson, count(*) as sales, sum(sale_total_rm) as sales_rm, avg(sale_total_rm) as avg_rm,
  median(days_first_contact_to_close) as median_days_to_close
from ${ff} group by 1 order by 3 desc limit 10
```

```sql segments
select segment, customer_groups, sales_rm, sales_rm / nullif(customer_groups, 0) as sales_per_customer from nomobug.customer_segments order by sales_rm desc
```

<div class="hero">
  <h1>Sales & customers</h1>
  <p>Filter by period, premise, area, package and client type. Every chart below follows the filters. Sales are recorded package prices, not cash received or profit.</p>
  <span class="chip">Area figures include only sales with a reliable district</span>
</div>

<div class="card">
<h3>Filters</h3>
<DateRange name=period data={detail} dates=month end={new Date()} defaultValue="Last 12 Months"/>
<Dropdown name=premise data={premises} value=premise title="Premise" multiple=true selectAllByDefault=true/>
<Dropdown name=package data={packages_list} value=package_group title="Package" multiple=true selectAllByDefault=true/>
<Dropdown name=area data={areas_list} value=area title="Area" multiple=true selectAllByDefault=true/>
<ButtonGroup name=area_mode title="Include sales without an area">
  <ButtonGroupItem valueLabel="Yes" value="all" default/>
  <ButtonGroupItem valueLabel="Only selected areas" value="selected"/>
</ButtonGroup>
<ButtonGroup name=client title="Client">
  <ButtonGroupItem valueLabel="All" value="%" default/>
  <ButtonGroupItem valueLabel="New" value="New client"/>
  <ButtonGroupItem valueLabel="Returning" value="Returning client"/>
</ButtonGroup>
</div>

<div class="kpis">
  <BigValue data={kpi} value=sales_rm title="Sales" fmt='"RM"#,##0'/>
  <BigValue data={kpi} value=sales title="Packages sold" fmt="#,##0"/>
  <BigValue data={kpi} value=avg_sale title="Average sale" fmt='"RM"#,##0'/>
  <BigValue data={kpi} value=residential_share title="Residential share of sales" fmt=pct0/>
</div>

<div class="card">
  <h3>Sales by month</h3>
  <p class="sub">Residential vs commercial, selected period</p>
  <BarChart data={trend} x=month y=sales_rm series=premise type=stacked yFmt='"RM"#,##0' xFmt="mmm yy" chartAreaHeight=240/>
</div>

<div class="row2">
  <div class="card">
    <h3>Top packages</h3>
    <p class="sub">By sales, selected filters</p>
    <DataTable data={top_packages} rowShading=false rows=10>
      <Column id=package title="Package"/>
      <Column id=sales title="Sold"/>
      <Column id=sales_rm title="Sales" fmt='"RM"#,##0' contentType=bar barColor="#DCDDF4"/>
      <Column id=avg_rm title="Average" fmt='"RM"#,##0'/>
    </DataTable>
  </div>
  <div class="card">
    <h3>Sales by area</h3>
    <p class="sub">Top 12 areas with a known district</p>
    <BarChart data={by_area} x=area y=sales_rm swapXY=true yFmt='"RM"#,##0' colorPalette={['#5B63C9']} chartAreaHeight=300 labels=true yAxisLabels=false yGridlines=false yMax={Math.max(...by_area.map(d => d.sales_rm ?? 0)) * 1.25}/>
  </div>
</div>

<div class="row3">
  <div class="card">
    <h3>Residential vs commercial</h3>
    <BarChart data={by_premise} x=premise y=sales_rm yFmt='"RM"#,##0' colorPalette={['#3FA27A']} chartAreaHeight=200 labels=true/>
  </div>
  <div class="card">
    <h3>New vs returning clients</h3>
    <BarChart data={client_mix} x=client_type y=sales_rm yFmt='"RM"#,##0' colorPalette={['#D9577A']} chartAreaHeight=200 labels=true/>
  </div>

  <div class="card">
    <h3>Pests treated</h3>
    <DataTable data={pests} rowShading=false rows=8>
      <Column id=pest title="Pest" wrap=true/>
      <Column id=sales_rm title="Sales" fmt='"RM"#,##0' contentType=bar barColor="#F4D9C6"/>
    </DataTable>
  </div>
</div>

## Customer segments

<div class="row2">
  <div class="card">
    <h3>Customer groups</h3>
    <p class="sub">All recorded history. Repeat customers bought more than one programme.</p>
    <DataTable data={segments} rowShading=false>
      <Column id=segment title="Segment"/>
      <Column id=customer_groups title="Customers"/>
      <Column id=sales_rm title="Sales" fmt='"RM"#,##0'/>
      <Column id=sales_per_customer title="Per customer" fmt='"RM"#,##0'/>
    </DataTable>
  </div>
  <div class="card">
    <h3>How customers pay</h3>
    <p class="sub">Billing arrangement, selected filters</p>
    <BarChart data={billing_mix} x=billing y=sales_rm swapXY=true yFmt='"RM"#,##0' colorPalette={['#B8901A']} chartAreaHeight=200 labels=true yAxisLabels=false yGridlines=false yMax={Math.max(...billing_mix.map(d => d.sales_rm ?? 0)) * 1.25}/>
  </div>
</div>

<div class="card">
  <h3>Sales by salesperson</h3>
  <p class="sub">Selected filters · days to close = median days from first contact to sale</p>
  <DataTable data={salespeople} rowShading=false rows=10>
    <Column id=salesperson title="Salesperson"/>
    <Column id=sales title="Sales"/>
    <Column id=sales_rm title="Sales value" fmt='"RM"#,##0' contentType=bar barColor="#DCDDF4"/>
    <Column id=avg_rm title="Average" fmt='"RM"#,##0'/>
    <Column id=median_days_to_close title="Days to close" fmt="#,##0"/>
  </DataTable>
</div>


## Prospect conversations

```sql prospect_months
select * from nomobug.prospects where month between '${inputs.period.start}' and '${inputs.period.end}' order by month
```
```sql prospect_dates
select sum(undated_first_reply_rows) as undated from nomobug.prospects
```

<div class="card">
<p class="sub">Recorded enquiry rows by first-reply month. Repeat conversations can belong to the same person; these are not unique customers or a sales-conversion funnel.</p>
<BarChart data={prospect_months} x=month y={['recorded_open_rows','recorded_closed_rows']} type=stacked xFmt="mmm yyyy" chartAreaHeight=220/>
<DataTable data={prospect_months}>
<Column id=month title="First reply" fmt="mmm yyyy"/>
<Column id=prospect_candidate_rows title="Enquiry rows"/>
<Column id=recorded_open_rows title="Open"/>
<Column id=recorded_closed_rows title="Closed"/>
<Column id=exact_won_remark_rows title="Marked won"/>
</DataTable>
<p class="sub"><Value data={prospect_dates} column=undated/> enquiry rows have no usable first-reply date and are excluded from the date-filtered chart. Closed does not necessarily mean a sale.</p>
</div>
