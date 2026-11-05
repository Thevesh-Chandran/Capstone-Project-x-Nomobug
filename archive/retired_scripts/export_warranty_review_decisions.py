"""Preserve reviewed event decisions without customer titles or free text."""
import argparse
import csv
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    args = parser.parse_args()
    frame = pd.read_excel(args.workbook, sheet_name='Review', engine='openpyxl')
    sample = json.loads((ROOT / 'tmp/warranty_label_review_rows.json').read_text(encoding='utf-8'))
    by_id = {row['review_id']: row for row in sample}
    valid = {'Confirmed warranty claim', 'Not a warranty claim', 'Unclear'}
    if frame['Review ID'].duplicated().any() or set(frame['Review ID']) != set(by_id):
        raise ValueError('Workbook does not match the preserved review sample')
    if not set(frame['Review label']).issubset(valid):
        raise ValueError('Review contains missing or invalid labels')
    output = ROOT / 'planning/warranty_review_decisions.csv'
    with output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            'review_id', 'calendar_event_row', 'event_id', 'review_label',
            'original_system_positive', 'review_stratum', 'confidence',
        ])
        writer.writeheader()
        for row in frame.to_dict('records'):
            original = by_id[row['Review ID']]
            writer.writerow({
                'review_id': row['Review ID'],
                'calendar_event_row': original['calendar_event_row'],
                'event_id': original['event_id'],
                'review_label': row['Review label'],
                'original_system_positive': original['system_label'],
                'review_stratum': original['review_stratum'],
                'confidence': '' if pd.isna(row.get('Confidence')) else row['Confidence'],
            })
    print(f'Preserved {len(frame)} review decisions in {output}')


if __name__ == '__main__':
    main()
