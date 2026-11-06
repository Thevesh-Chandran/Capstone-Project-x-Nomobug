---
title: Maps & patterns
sidebar_position: 5
---

```sql areas
select area_cell, place, lat, lng, services, sales_records, return_visits,
       return_share,
       case when services >= 20 then 'Enough visits to compare' else 'Few visits' end as volume
from nomobug.spatial_area
order by services desc
```

```sql area_kpi
select count(*) as areas, sum(services) as services, sum(return_visits) as return_visits,
       sum(return_visits) / nullif(sum(services), 0) as return_share
from nomobug.spatial_area
```

```sql top_return_areas
select place, services, return_visits, return_share
from nomobug.spatial_area where services >= 20
order by return_share desc limit 10
```

```sql workload
select
  case when team ilike 'REPLACEMENT%' then 'Replacement' else trim(regexp_replace(regexp_replace(team, '^TEAM ', ''), ' *[(].*[)]', '')) end as team,
  ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][cast(dow as integer)] as day,
  cast(dow as integer) as dow,
  bookings, round(bookings / nullif(days, 0), 1) as per_day, return_visits
from nomobug.scheduling
where team not in ('SALES TEAM')
order by dow
```

```sql busiest
select day, sum(bookings) as bookings from ${workload} group by day, dow order by dow
```

<div class="hero">
  <h1>Maps & patterns</h1>
  <p>Where services happen and where return visits cluster, and how bookings spread across teams and days. Areas are grouped cells, never individual customer addresses.</p>
  <span class="chip">The interactive heat map and radius tool are below</span>
</div>

<div class="kpis">
  <BigValue data={area_kpi} value=areas title="Service areas mapped"/>
  <BigValue data={area_kpi} value=services title="Services in mapped areas" fmt="#,##0"/>
  <BigValue data={area_kpi} value=return_visits title="Return visits recorded" fmt="#,##0"/>
  <BigValue data={area_kpi} value=return_share title="Return-visit share" fmt=pct1/>
</div>

<div class="card">
  <h3>Service areas</h3>
  <p class="sub">Bubble size = services; colour = share of visits that were returns. Hover an area for its figures.</p>
  <BubbleMap data={areas} lat=lat long=lng size=services value=return_share valueFmt=pct0 pointName=place colorPalette={['#A3A8E6','#E8A46A','#E24A3F']} max=0.4 height=460 maxSize=28 startingLat=3.1 startingLong=101.62 startingZoom=10 basemap={`https://tile.openstreetmap.org/{z}/{x}/{y}.png`} attribution='© OpenStreetMap contributors' tooltipType=hover tooltip={[
    {id: 'place', showColumnName: false, valueClass: 'font-bold'},
    {id: 'services', title: 'Services'},
    {id: 'return_visits', title: 'Return visits'},
    {id: 'return_share', title: 'Return share', fmt: 'pct0'}
  ]}/>
</div>

<div class="row2">
  <div class="card">
    <h3>Bookings by team and day</h3>
    <p class="sub">Average bookings per working day, last 26 weeks</p>
    <Heatmap data={workload} x=day y=team value=per_day xSort=dow colorScale={['#EEF0FB','#5B63C9']} valueLabels=true chartAreaHeight=240/>
  </div>
  <div class="card">
    <h3>Areas with the highest return share</h3>
    <p class="sub">Areas with at least 20 services; hover the map above to find each one</p>
    <DataTable data={top_return_areas} rowShading=false rows=10>
      <Column id=place title="Area"/>
      <Column id=services title="Services"/>
      <Column id=return_visits title="Returns"/>
      <Column id=return_share title="Return share" fmt=pct0 contentType=bar barColor="#F3C5D1"/>
    </DataTable>
  </div>
</div>

<div class="card">
  <h3>Busiest days</h3>
  <p class="sub">Total bookings by day of week, all field teams, last 26 weeks</p>
  <BarChart data={busiest} x=day y=bookings sort=false colorPalette={['#2E9CB8']} chartAreaHeight=200 labels=true/>
</div>

<p class="note">Return visits are warranty claims booked in the calendar when pests come back after a treatment. Areas with few visits can show extreme shares by chance.</p>
