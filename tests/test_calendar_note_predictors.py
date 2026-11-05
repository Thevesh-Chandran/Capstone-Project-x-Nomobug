from scripts.test_calendar_note_predictors import extract

def test_free_notes_found():
    r=extract('Lipas banyak di kitchen\nclient kata lipas masih ada tapi berkurangan\nkita letak gel baiting then spray semua tempat')
    assert r['heavy_pest_mention']==1 and r['pest_improving_mention']==1 and r['pest_persisting_mention']==1
    assert r['gel_bait_mention']==1 and r['spray_mention']==1

def test_admin_and_template_are_not_observations():
    assert not any(extract('Name: Heavy Ant\nAddress: Spray Road\n(Masih ada masalah? Berkurangan?)\nWarranty claim: lipas banyak').values())

def test_no_severity_from_bait_quantity():
    r=extract('letak gel banyak dekat pintu')
    assert r['gel_bait_mention']==1 and r['heavy_pest_mention']==0

def test_restriction_remains_mention_not_delivered_treatment():
    r=extract('CANNOT SPRAY INSIDE CAR, ONLY BAITING')
    assert r['treatment_restriction_mention']==1 and r['spray_mention']==1
