from pathlib import Path
from scripts.release_business_analytics import business_output_version

ROOT=Path(__file__).resolve().parents[1]

def test_district_change_creates_new_immutable_sidecar_version():
    before={'sales':[{'district':'Unassigned','sales_rm':100}],'services':[]}
    after={'sales':[{'district':'Petaling','sales_rm':100}],'services':[]}
    assert business_output_version(ROOT,before,[])!=business_output_version(ROOT,after,[])

def test_warehouse_row_order_does_not_change_version():
    a={'sales':[{'district':'A'},{'district':'B'}],'services':[]}
    b={'sales':list(reversed(a['sales'])),'services':[]}
    assert business_output_version(ROOT,a,[])==business_output_version(ROOT,b,[])
