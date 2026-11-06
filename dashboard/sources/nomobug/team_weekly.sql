select date(week_start) as week, team, sum(bookings) as bookings from `profound-keel-500007-s4.gold.dashboard_team_workload` group by 1,2 order by 1
