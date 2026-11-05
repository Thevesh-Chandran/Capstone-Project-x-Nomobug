import json
from pathlib import Path
from webapp.spatial import location, payload


def test_invalid_and_ambiguous_coordinates_are_not_exposed():
    for value in (None, {}, {'latitude':float('nan'),'longitude':101,'uncertainty_km':0},
                  {'latitude':3,'longitude':101,'uncertainty_km':-1}):
        assert location(value) is None


def test_map_payload_preserves_decisions_without_raw_risk_probabilities():
    point={'latitude':3.1,'longitude':101.5,'uncertainty_km':.2}
    business={'records':{'sales':[],'appointments':[]},'receipt':{'published_release':'test'}}
    evaluated=[dict(point,score=.172,threshold=.15,outcome=1,global_review=True),
               dict(point,score=.1,threshold=.15,outcome=0,global_review=False)]
    result=payload(business,{'fetched_at_utc':'test'},evaluated,{'features':[]})
    assert [r['score'] for r in result['model']]==[1,0]
    assert result['model_total']==2
    assert '.172' not in json.dumps(result)


def test_production_map_has_no_embedded_private_snapshot_or_inline_scripts():
    html=(Path(__file__).resolve().parents[1]/'webapp/static/maps.html').read_text(encoding='utf-8')
    assert '__REVIEWED_DATA__' not in html and '<script>' not in html
    assert '<style>' not in html
    assert '/maps.js' in html and '/maps.css' in html
