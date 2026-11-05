"""Label CP2 datasets and inventory dependencies without renaming live IDs."""
import json
from pathlib import Path
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'profound-keel-500007-s4'

def main():
    client = bigquery.Client(project=PROJECT)
    records = []
    roles = {'gold': ('management', 'Management dashboard sources'),
             'silver': ('transforms', 'Cleaned business records'),
             'bronze': ('source', 'Immutable source snapshots'),
             'audit': ('audit', 'Pipeline run and release evidence'),
             'analytics_ml': ('models', 'Model research and evaluation')}
    for item in client.list_datasets():
        dataset = client.get_dataset(item.reference)
        name = dataset.dataset_id
        role, title = roles.get(name, ('release', 'Versioned reporting release'))
        if name.startswith('cp2qa_'):
            role, title = 'qa', 'Historical reporting validation'
        elif name not in roles and not name.startswith('cp2r_'):
            records.append({'dataset': name, 'role': 'unclassified', 'changed': False})
            continue
        before = {'friendly_name': dataset.friendly_name, 'labels': dataset.labels}
        dataset.friendly_name = title + (' — ' + name if role in {'release','qa'} else '')
        dataset.labels = {**(dataset.labels or {}), 'cp2_role': role, 'cp2_project': 'nomobug'}
        client.update_dataset(dataset, ['friendly_name', 'labels'])
        records.append({'dataset': name, 'role': role, 'before': before,
                        'friendly_name': dataset.friendly_name, 'changed': True})
    views = []
    for table in client.list_tables(PROJECT + '.gold'):
        resource = client.get_table(table.reference)
        views.append({'table': resource.table_id, 'type': resource.table_type,
                      'sql': resource.view_query if resource.table_type == 'VIEW' else None})
    destination = ROOT / 'outputs/project_audit/20261016_cleanup/bigquery_catalog.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({'datasets': records, 'gold_objects': views,
                                      'deleted': [], 'renamed_ids': []}, indent=2))
    print(json.dumps({'datasets_labelled': sum(r['changed'] for r in records),
                      'gold_objects': len(views), 'receipt': str(destination)}))

if __name__ == '__main__':
    main()
