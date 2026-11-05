"""Decorative Looker page frames: no sample charts or invented KPI values."""
from pathlib import Path
import json
from build_dashboard_mockups import Canvas, TITLES, SUBS, SCOPES, C, W, H, Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/dashboard_design/20261010_native_build/frames'
OUT.mkdir(parents=True, exist_ok=True)
layout = json.loads((ROOT / 'outputs/dashboard_design/20261004_complete_guide/layout_coordinates.json').read_text())
for i, title in enumerate(TITLES):
    c = Canvas(i)
    c.rect((0, 0, 210, H), 'white', 0)
    c.line([(210, 0), (210, H)])
    c.rect((25, 32, 62, 69), 'ink', 9)
    c.text(36, 40, 'N', 22, 'white', True)
    c.text(73, 36, 'NOMObug', 21, bold=True)
    c.text(74, 61, 'Management', 11, 'muted')
    c.text(26, 119, 'BUSINESS REPORT', 10, 'muted', True)
    for n, label in enumerate(TITLES):
        y = 155 + n * 57
        if n == i:
            c.rect((14, y-7, 197, y+42), 'mint', 8)
        c.text(27, y+7, f'{n+1:02}', 11, 'green' if n == i else 'muted', True)
        c.text(55, y+5, label, 13, 'green' if n == i else 'muted', n == i, width=132)
    c.line([(25, 823), (185, 823)])
    c.text(26, 846, 'CP2 / 2026', 12, bold=True)
    c.text(26, 868, 'Management dashboard', 11, 'muted', width=150)
    c.rect((22, 966, 188, 1044), 'pale', 8)
    c.text(35, 980, 'Source-backed', 12, bold=True)
    c.text(35, 1002, 'Approved aggregate views', 11, 'muted', width=140)
    c.text(246, 29, 'REPORT / ' + ('VALIDATION' if i in (8, 9) else 'BUSINESS'), 11, 'muted', True)
    c.text(246, 57, title, 34, bold=True)
    c.text(246, 106, SUBS[i], 15, 'muted')
    c.pill(1290, 30, f'PAGE {i+1:02} / 13', 'white', 'muted', 137)
    if i in (5, 6, 8, 9, 10):
        c.rect((1250, 74, 1564, 118), 'white', 8, 'line')
        c.text(1267, 90, SCOPES[i], 13, 'ink', True)
    c.line([(246, 143), (1564, 143)])
    for n, b in enumerate(layout['pages'][title]):
        x, y, w, h = (b[k] for k in ('x', 'y', 'width', 'height'))
        navy = (i == 0 and n == 0) or (i == 8 and n == 0) or (i == 10 and n == 0)
        c.rect((x, y, x+w, y+h), 'ink' if navy else 'white', 16 if navy else 12, None if navy else 'line')
        if '/' not in b['title']:
            heading = b['title'].replace('Callbacks found', 'Warranty cases found').replace('Return cases found', 'Warranty cases found')
            c.text(x+24, y+22, heading, 18, 'white' if navy else 'ink', True, width=w-48)
    c.line([(246, 1048), (1564, 1048)])
    c.text(246, 1064, 'NOMObug · Recorded source data; review definitions and coverage on Data checks.', 11, 'muted')
    c.text(1300, 1064, 'Management', 11, 'muted')
    c.im.resize((W, H), Image.Resampling.LANCZOS).save(OUT / f'page_{i+1:02}_frame.png')
print(f'Created {len(TITLES)} decorative frames in {OUT}')
