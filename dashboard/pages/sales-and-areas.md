---
title: Sales & areas
sidebar_position: 4
---

```sql area_sales
select regexp_replace(coalesce(nullif(split_part(district, ' / ', 2), ''), district), '^W\.P\. ', '') as area,
       sales_rm, sales, sales_rm / nullif(sales, 0) as avg_sale_rm
from nomobug.area_sales order by sales_rm desc
```

```sql pest_groups
select * from nomobug.pest_groups order by sales_rm desc limit 8
```

```sql sales_monthly
select * from nomobug.sales_monthly
where month >= date_trunc('month', current_date - interval 24 month) and month < date_trunc('month', current_date)
order by month
```

```sql totals
select a.sales_rm, a.sales, a.sales_rm / nullif(a.sales, 0) as avg_sale, t.area as top_area
from (select sum(sales_rm) as sales_rm, sum(sales) as sales from nomobug.area_sales) a
cross join (select * from ${area_sales} limit 1) t
```

```sql packages_kpi
select m.month, m.packages, sum(m.packages) over () as packages_24m from ${sales_monthly} m order by month
```

<div class="hero">
  <h1>Sales & areas</h1>
  <p>Where sales come from and what customers buy. Area figures only include sales with a reliable district; the rest are left out rather than guessed.</p>
  <span class="chip">Recorded package prices, not cash received or profit</span>
</div>

<div class="kpis">
  <BigValue data={totals} value=sales_rm title="Sales with a known area, 12 months" fmt='"RM"#,##0'/>
  <BigValue data={totals} value=sales title="Purchases with a known area"/>
  <BigValue data={totals} value=avg_sale title="Average sale" fmt='"RM"#,##0'/>
  <BigValue data={packages_kpi} value=packages_24m title="Packages sold, 24 months" sparkline=month sparklineColor="#8B54D4"/>
</div>

<div class="row2">
  <div class="card">
    <h3>Sales by area</h3>
    <p class="sub">Last 12 months · top area: <Value data={totals} column=top_area/></p>
    <BarChart data={area_sales} x=area y=sales_rm swapXY=true yFmt='"RM"#,##0' colorPalette={['#2C6BE7']} chartAreaHeight=320/>
  </div>
  <div class="card">
    <h3>Sales by pest group</h3>
    <p class="sub">Top 8 groups, all recorded sales</p>
    <BarChart data={pest_groups} x=pest_group y=sales_rm swapXY=true yFmt='"RM"#,##0' colorPalette={['#009778']} chartAreaHeight=320/>
  </div>
</div>

<div class="card">
  <h3>Monthly sales and packages</h3>
  <p class="sub">Last 24 full months</p>
  <BarChart data={sales_monthly} x=month y=sales_rm y2=packages y2SeriesType=line yFmt='"RM"#,##0' xFmt="mmm yy" colorPalette={['#2C6BE7','#E78C08']} chartAreaHeight=240/>
</div>

<div class="card">
  <h3>Area details</h3>
  <DataTable data={area_sales} rowShading=false rows=15>
    <Column id=area title="Area"/>
    <Column id=sales_rm title="Sales" fmt='"RM"#,##0' contentType=bar barColor="#C3E0FD"/>
    <Column id=sales title="Purchases"/>
    <Column id=avg_sale_rm title="Average sale" fmt='"RM"#,##0'/>
  </DataTable>
</div>
