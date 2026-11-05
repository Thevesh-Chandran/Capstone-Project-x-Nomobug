from scripts.resolve_unmapped_purchase_batch import safe_peer

ADDRESS='12 Jalan Melati 3 Taman Bunga Indah 40100 Shah Alam Selangor'

def peer(address=ADDRESS,lat=3.1,lon=101.5):
    return {'input_address':address,'latitude':lat,'longitude':lon}

def test_same_address_peer_can_be_reused():
    assert safe_peer(ADDRESS,[peer()]) is not None

def test_different_postcode_is_not_reused():
    assert safe_peer(ADDRESS,[peer(ADDRESS.replace('40100','50100'))]) is None

def test_different_house_number_is_not_reused():
    assert safe_peer(ADDRESS,[peer(ADDRESS.replace('12 Jalan','91 Jalan'))]) is None

def test_conflicting_same_address_coordinates_remain_unresolved():
    assert safe_peer(ADDRESS,[peer(),peer(lat=3.5)]) is None
