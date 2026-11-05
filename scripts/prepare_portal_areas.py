"""Prepare aggregate district evaluation from saved historical predictions."""
import argparse
import json
from pathlib import Path
from webapp.geography import build

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('outputs/portal'));args=p.parse_args()
    result=build(Path(__file__).resolve().parents[1],args.output)
    print(json.dumps({'services':result['overall']['services'],'district_groups':len(result['districts']),
        'unassigned_services':sum(d['services'] for d in result['districts'] if d['district']=='Unassigned')}))
