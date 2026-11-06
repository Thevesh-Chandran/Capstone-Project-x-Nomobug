select pest_group, sum(recorded_package_face_value_rm) as sales_rm, sum(countable_package_rows) as packages from `profound-keel-500007-s4.gold.dashboard_sales_pest_groups` group by 1 order by 2 desc
