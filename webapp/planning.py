"""Read-only presentation of independently logged planning forecasts."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path

EVIDENCE=Path(__file__).parent/'models/planning_v1.json'

def load(folder,now=None):
    now=now or datetime.now(timezone.utc)
    evidence=json.loads(EVIDENCE.read_text(encoding='utf-8'))
    path=Path(folder)/'planning_forecast.json'
    live={'status':'not_connected','forecasts':[],'evaluation':[],
          'message':'The new weekly collection has not yet been verified.'}
    if path.exists():
        try:
            value=json.loads(path.read_text(encoding='utf-8'))
            if value.get('version')!='planning_v1' or value.get('protocol_sha256')!=evidence['protocol_sha256']:
                raise ValueError('Planning protocol differs')
            updated=datetime.fromisoformat(value['updated_at'].replace('Z','+00:00'))
            value['stale']=now-updated>timedelta(days=8)
            if value.get('latest'):
                origin=datetime.fromisoformat(value['latest']['origin'])
                value['forecast_for_current_cycle']=origin<=now<origin+timedelta(days=7)
            first=datetime.fromisoformat(evidence['first_origin']+'T00:00:00+08:00')
            value['collection_overdue']=now>=first and (not value.get('latest') or now>=datetime.fromisoformat(value['latest']['origin'])+timedelta(days=7))
            live=value
        except (ValueError,KeyError,TypeError):
            live['message']='The planning record could not be verified. Historical evidence is still available.'
    return {'evidence':evidence,'live':live}
