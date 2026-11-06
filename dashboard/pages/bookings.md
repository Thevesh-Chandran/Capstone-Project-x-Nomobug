---
title: Bookings & staffing
sidebar_position: 3
---

```sql bookings
select * from nomobug.forecast where forecast_id = 'booking_entries_h2'
```

```sql hours
select * from nomobug.forecast where forecast_id = 'booked_hours_h1'
```

```sql staffing
select * from nomobug.staffing
```

```sql forecast
select * from nomobug.forecast
```

```sql backtest_long
select period_start, 'Actual' as series, actual_bookings as bookings from nomobug.backtest
union all select period_start, 'Model forecast', model_forecast_bookings from nomobug.backtest
union all select period_start, 'Simple average', simple_average_bookings from nomobug.backtest
order by period_start
```

```sql accuracy
select avg(abs(model_forecast_bookings - actual_bookings)) as model_error,
       avg(abs(simple_average_bookings - actual_bookings)) as simple_error
from nomobug.backtest
```

```sql team_weekly
select * replace (trim(case when team ilike 'REPLACEMENT%' then 'Replacement' else regexp_replace(regexp_replace(team, '^TEAM ', ''), ' *[(].*[)]', '') end) as team)
from nomobug.team_weekly
where team <> 'SALES TEAM' and week >= current_date - interval 12 week
order by week
```

```sql team_total
select team, sum(bookings) as bookings from ${team_weekly} group by 1 order by 2 desc
```

<div class="hero">
  <h1>Bookings & staffing</h1>
  <p>How busy the next weeks look, and how many staff hours to plan. Every forecast comes with a likely range based on how far past forecasts were off.</p>
  <span class="chip">Forecast issued weekly · model estimates, not guarantees</span>
</div>

<div class="kpis">
  <BigValue data={bookings} value=prediction title="Bookings, next 2 weeks" fmt="#,##0"/>
  <BigValue data={hours} value=prediction title="Appointment hours, next week" fmt="#,##0"/>
  <BigValue data={staffing} value=suggested_staff_hours title="Staff hours to plan" fmt="#,##0"/>
  <BigValue data={staffing} value=hours_to_keep_open title="Hours to keep open" fmt="#,##0"/>
</div>

<div class="row3">
  <div class="action">
    <div class="label">Likely range</div>
    <div class="big"><Value data={bookings} column=likely_low fmt="#,##0"/> to <Value data={bookings} column=likely_high fmt="#,##0"/> bookings</div>
    <p><Value data={bookings} column=already_booked fmt="#,##0"/> were already booked when the forecast was made.</p>
  </div>
  <div class="action green">
    <div class="label">Staffing plan</div>
    <div class="big"><Value data={staffing} column=suggested_action/></div>
    <p>Includes a buffer of <Value data={staffing} column=buffer_hours fmt="#,##0"/> hours for forecast error.</p>
  </div>
  <div class="action amber">
    <div class="label">Accuracy</div>
    <div class="big">Off by about <Value data={accuracy} column=model_error fmt="#,##0"/> bookings</div>
    <p>A simple average was off by <Value data={accuracy} column=simple_error fmt="#,##0"/> on the same weeks.</p>
  </div>
</div>

<div class="card">
  <h3>Forecast vs actual bookings</h3>
  <p class="sub">Two-week booking forecasts on past weeks, against what was actually booked</p>
  <LineChart data={backtest_long} x=period_start y=bookings series=series xFmt="d mmm" seriesOrder={['Actual','Model forecast','Simple average']} colorPalette={['#0F141D','#2C6BE7','#E78C08']} chartAreaHeight=240 markers=true/>
</div>

<div class="row2">
  <div class="card">
    <h3>Bookings per team</h3>
    <p class="sub">Last 12 weeks, field teams</p>
    <BarChart data={team_weekly} x=week y=bookings series=team type=stacked xFmt="d mmm" chartAreaHeight=220/>
  </div>
  <div class="card">
    <h3>Team share, last 12 weeks</h3>
    <p class="sub">Total recorded bookings per team</p>
    <BarChart data={team_total} x=team y=bookings swapXY=true colorPalette={['#2C6BE7']} chartAreaHeight=220 labels=true yAxisLabels=false yGridlines=false yMax={Math.max(...team_total.map(d => d.bookings ?? 0)) * 1.25}/>
  </div>
</div>

<div class="card">
  <h3>Forecast details</h3>
  <DataTable data={forecast} rowShading=false>
    <Column id=title title="Forecast"/>
    <Column id=period_start title="From" fmt="d mmm"/>
    <Column id=period_end title="To" fmt="d mmm"/>
    <Column id=prediction title="Expected" fmt="#,##0.0"/>
    <Column id=likely_low title="Low" fmt="#,##0"/>
    <Column id=likely_high title="High" fmt="#,##0"/>
    <Column id=already_booked title="Booked so far" fmt="#,##0"/>
  </DataTable>
</div>
