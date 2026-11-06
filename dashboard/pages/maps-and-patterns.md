---
title: Maps & patterns
sidebar_position: 5
---

```sql areas
select area_cell, place, lat, lng, services, sales_records, return_visits,
       return_share,
       case when services >= 20 then 'Enough visits to compare' else 'Few visits' end as volume
from nomobug.spatial_area
where services >= ${inputs.mp_min}
order by services desc
```

```sql area_kpi
select count(*) as areas, sum(services) as services, sum(return_visits) as return_visits,
       sum(return_visits) / nullif(sum(services), 0) as return_share
from nomobug.spatial_area
```

```sql top_return_areas
select place, services, return_visits, return_share
from nomobug.spatial_area where services >= ${inputs.mp_min}
order by return_share desc limit 10
```

```sql workload_all
select
  case when team ilike 'REPLACEMENT%' then 'Replacement' else trim(regexp_replace(regexp_replace(team, '^TEAM ', ''), ' *[(].*[)]', '')) end as team,
  ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][cast(dow as integer)] as day,
  cast(dow as integer) as dow,
  bookings, round(bookings / nullif(days, 0), 1) as per_day, return_visits
from nomobug.scheduling
where team not in ('SALES TEAM')
order by dow
```

```sql mp_teams
select distinct team from ${workload_all} order by 1
```

```sql workload
select * from ${workload_all} where team in ${inputs.mp_team.value} order by dow
```

```sql busiest
select day, sum(bookings) as bookings from ${workload} group by day, dow order by dow
```

<div class="hero">
  <h1>Maps & patterns</h1>
  <p>Where services happen and where return visits cluster, and how bookings spread across teams and days. Areas are grouped cells, never individual customer addresses.</p>
  <span class="chip">The interactive heat map and radius tool are below</span>
</div>

<div class="card filters">
<ButtonGroup name=mp_min title="Minimum services per area (map and table)">
  <ButtonGroupItem valueLabel="Any" value=1/>
  <ButtonGroupItem valueLabel="10+" value=10/>
  <ButtonGroupItem valueLabel="20+" value=20 default/>
  <ButtonGroupItem valueLabel="40+" value=40/>
</ButtonGroup>
<Dropdown name=mp_team data={mp_teams} value=team title="Team (heat map and busiest days)" multiple=true selectAllByDefault=true/>
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
    <p class="sub">Areas with at least the selected number of services; hover the map above to find each one</p>
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
  <p class="sub">Total bookings by day of week, selected teams, last 26 weeks</p>
  <BarChart data={busiest} x=day y=bookings sort=false colorPalette={['#2E9CB8']} chartAreaHeight=200 labels=true/>
</div>

