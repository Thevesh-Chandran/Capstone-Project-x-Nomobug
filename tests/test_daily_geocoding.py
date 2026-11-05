from datetime import datetime,timedelta,timezone
from scripts import cp2_geocoding as g

ADDRESS='No 18 Jalan P8G1, Presint 8, Putrajaya'

def event(address=ADDRESS,title='GPC 1/3 Example',status='confirmed'):
 return {'calendar_event_row':1,'summary':title,'status':status,'description':'Nama: Private Person\nAlamat: '+address+'\nPhone: 0123456789','location':'','start_raw':'2026-10-17T10:00:00+08:00','end_raw':'2026-10-17T11:00:00+08:00','calendar_id':'test','event_id':'test'}

def test_candidate_extraction_sends_only_sanitized_address_and_reuses_hash():
 found,counts=g.candidates([event()],[{'source_column_007':'CUST1','source_column_011':ADDRESS}])
 assert len(found)==1
 item=next(iter(found.values()))
 assert item['address']==ADDRESS
 assert 'Private Person' not in item['address'] and '0123456789' not in item['address']
 assert item['event_rows']==[1]
 assert g.address_key(ADDRESS)==next(iter(found))

def test_cancelled_events_do_not_create_new_geocoding_requests():
 assert not g.candidates([event(title='CANCELLED GPC 1/3')],[])[0]
 assert not g.candidates([event(status='cancelled')],[])[0]
 assert not g.service_candidate(event(title='INSPECTION 1/1'))
 assert g.service_candidate(event(title='GPC Warranty Example'))

def test_known_manual_geocode_is_not_requested_or_replaced():
 key=g.address_key(ADDRESS);found={key:{'address':ADDRESS,'priority':'2026','event_rows':[1]}}
 cache={key:{'status':'accepted','manual_override_protected':True,'latitude':3.,'longitude':101.}}
 def blocked(*args):raise AssertionError('cached address must not call provider')
 updates,summary=g.perform(found,cache,'private',transport=blocked,sleep=lambda _:None)
 assert not updates and summary['reused_cached_addresses']==1
 assert cache[key]['manual_override_protected']

def test_provider_failures_are_retryable_without_secret_or_address_in_cache():
 key=g.address_key(ADDRESS);found={key:{'address':ADDRESS,'priority':'2026','event_rows':[1]}};cache={}
 def fail(*args):raise g.geo.GeoapifyRequestError('HTTP 429')
 updates,summary=g.perform(found,cache,'SECRET_API_KEY',transport=fail,sleep=lambda _:None)
 assert summary['errors']==1 and summary['attempted']==1
 assert not g.due(updates[0],datetime.now(timezone.utc))
 assert g.due(updates[0],datetime.now(timezone.utc)+timedelta(days=2))
 assert 'SECRET_API_KEY' not in str(updates) and ADDRESS not in str(updates)

def test_no_result_is_reviewable_not_repeated_daily_and_limit_is_obeyed():
 found={str(i):{'address':ADDRESS,'priority':'2026','event_rows':[]} for i in range(3)};cache={}
 updates,summary=g.perform(found,cache,'private',max_requests=2,transport=lambda *args:{'result_count':0},sleep=lambda _:None)
 assert summary['attempted']==2 and summary['pending_after']==1
 assert all(r['status']=='no_result' and not g.due(r,datetime.now(timezone.utc)) for r in updates)
 assert all('input_address' not in r and 'formatted' not in r for r in updates)

def test_address_change_has_a_different_cache_key():
 assert g.address_key(ADDRESS)!=g.address_key(ADDRESS.replace('18','19'))
 assert g.clean_address('Alamat tepat akan diberi') is None

def test_recent_sales_year_is_prioritized_without_guessing_an_ambiguous_date():
 rows=[{'source_column_007':'CUST1','source_column_011':ADDRESS,'source_column_004':'10/1/2024'}, {'source_column_007':'CUST2','source_column_011':ADDRESS.replace('18','19'),'source_column_004':'10/1/2026'}, {'source_column_007':'CUST3','source_column_011':ADDRESS.replace('18','20'),'source_column_004':'Pending'}]
 found,_=g.candidates([],rows)
 assert found[g.address_key(ADDRESS)]['priority']=='2024-01-01'
 assert found[g.address_key(ADDRESS.replace('18','19'))]['priority']=='2026-01-01'
 assert found[g.address_key(ADDRESS.replace('18','20'))]['priority']==''

def test_malformed_geocoding_flag_fails_before_any_source_access(monkeypatch):
 from scripts import cp2_reporting_release as release
 import pytest
 monkeypatch.setenv('NOMOBUG_BQ_UPLOAD_APPROVED','yes')
 monkeypatch.setenv('CP2_GEOCODING_ENABLED','yes OTHER=100')
 with pytest.raises(ValueError,match='exactly yes or no'):release.run()

def test_description_notes_and_team_names_are_not_part_of_geocoding_input():
 e=event();e['description']='Nama: Private Person\nAlamat: '+ADDRESS+'\nTEAM CHARLIE (Private Technician)\nNotes: gate code 123456'
 found,_=g.candidates([e],[])
 assert next(iter(found.values()))['address']==ADDRESS
 assert 'Private' not in str([r['address'] for r in found.values()])

def test_address_block_stops_at_blank_line_before_private_notes():
 e=event();e['description']='Alamat: '+ADDRESS+'\n\nPlease contact Private Person before visiting'
 found,_=g.candidates([e],[])
 assert next(iter(found.values()))['address']==ADDRESS
def test_named_sales_building_uses_explicit_address_field():
    from scripts.cp2_geocoding import clean_sales_address,address_key
    address='B South Service Apartments, Bangsar South'
    assert clean_sales_address(address)==address
    assert address_key(address,explicit_address_field=True)

def test_unit_led_sales_address_is_idempotent_and_has_same_labelled_hash():
    from scripts.cp2_geocoding import clean_sales_address,address_key
    address='G-62, Jalan SG Prima 3/1, Prima Sri Gombak'
    cleaned=clean_sales_address(address)
    assert cleaned==address
    assert clean_sales_address(cleaned)==cleaned
    assert address_key(address,explicit_address_field=True)==address_key('Alamat: '+address)

def test_sales_field_still_strips_contacts_and_secrets():
    from scripts.cp2_geocoding import clean_sales_address
    value='B South Service Apartments, Bangsar South Phone: 0123456789 Access code: private'
    clean=clean_sales_address(value)
    assert clean and '0123456789' not in clean and 'private' not in clean

def test_sales_cache_keeps_legacy_point_while_new_key_is_pending():
    from scripts.cp2_geocoding import sales_cache_record,address_key
    address='Residency East 12 Jalan Melati 3 Taman Bunga 40100 Shah Alam'
    old={'status':'accepted','precision_tier':'street_candidate','latitude':3.1,'longitude':101.5}
    cache={address_key(address):old}
    assert sales_cache_record(cache,address)==old

