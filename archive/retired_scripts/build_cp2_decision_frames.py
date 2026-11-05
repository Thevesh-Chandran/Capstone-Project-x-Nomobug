"""Decorative frame for the source-backed management action page; no KPI data."""
from pathlib import Path
from scripts.build_dashboard_mockups import Canvas, TITLES, W, H, Image

out = Path(__file__).resolve().parents[1] / 'outputs/dashboard_design/20261011_decisions'
out.mkdir(parents=True, exist_ok=True)
c = Canvas(0)
c.rect((0, 0, 210, H), 'white', 0)
c.rect((25, 32, 62, 69), 'ink', 9)
c.text(36, 40, 'N', 22, 'white', True)
c.text(73, 36, 'NOMObug', 21, bold=True)
c.text(74, 61, 'Management', 11, 'muted')
c.text(26, 119, 'BUSINESS REPORT', 10, 'muted', True)
for n, label in enumerate([*TITLES, 'Actions to review']):
    y = 155 + n * 53
    if n == 11: c.rect((14, y-7, 197, y+42), 'mint', 8)
    c.text(27, y+7, f'{n+1:02}', 11, 'green' if n == 11 else 'muted', True)
    c.text(55, y+5, label, 13, 'green' if n == 11 else 'muted', n == 11, width=132)
c.text(246, 29, 'REPORT / NEXT ACTIONS', 11, 'muted', True)
c.text(246, 57, 'Actions to review', 34, bold=True)
c.text(246, 106, 'Source-backed checks for the next seven days and recorded contract balances', 15, 'muted')
c.rect((246, 166, 1564, 324), 'ink', 16)
c.text(274, 192, 'Check the source before contacting a client', 27, 'white', True)
c.text(274, 242, 'Reminders are planned dates. Bookings are scheduled visits. A remaining balance is not proof of overdue payment.', 21, 'white', width=1240)
c.rect((246, 350, 1564, 1008), 'white', 12, 'line')
c.text(270, 373, 'What needs a review?', 22, bold=True)
c.text(270, 415, 'Counts use different units; do not add categories together. Use the category filter to focus the list.', 18, 'muted')
c.text(246, 1050, 'Restricted management report · Aggregate records only · Source age is flagged after 36 hours.', 15, 'muted')
c.im.resize((W,H),Image.Resampling.LANCZOS).save(out/'actions_frame.png')
print(out/'actions_frame.png')

c = Canvas(0)
c.rect((0, 0, 210, H), 'white', 0)
c.rect((25, 32, 62, 69), 'ink', 9)
c.text(36, 40, 'N', 22, 'white', True)
c.text(73, 36, 'NOMObug', 21, bold=True)
c.text(74, 61, 'Management', 11, 'muted')
c.text(26, 119, 'BUSINESS REPORT', 10, 'muted', True)
for n, label in enumerate([*TITLES, 'Actions to review', 'Model comparisons']):
    y = 155 + n * 49
    if n == 12: c.rect((14, y-7, 197, y+37), 'mint', 8)
    c.text(27, y+7, f'{n+1:02}', 11, 'green' if n == 12 else 'muted', True)
    c.text(55, y+5, label, 13, 'green' if n == 12 else 'muted', n == 12, width=132)
c.text(246, 29, 'REPORT / DEVELOPMENT EVIDENCE', 11, 'muted', True)
c.text(246, 57, 'Model comparisons', 34, bold=True)
c.text(246, 106, 'What additional inputs and a simple follow-up rule contribute', 15, 'muted')
for x,w,title in [(246,640,'Do environmental inputs help?'),(910,654,'Compare with a simple rule')]:
    c.rect((x,166,x+w,926),'white',12,'line')
    c.text(x+24,192,title,25,bold=True,width=w-48)
c.text(270,246,'Three historical development folds',19,'muted')
c.text(934,246,'Same number of reviews for every method',19,'muted')
c.rect((246,946,1564,1024),'ink',12)
c.text(272,970,'Development evidence explains choices. Future accuracy and fewer warranty visits have not been established.',22,'white',width=1260)
c.text(246,1050,'Restricted management report · Aggregate evidence only · See Prediction model for the held-out test.',15,'muted')
c.im.resize((W,H),Image.Resampling.LANCZOS).save(out/'comparisons_frame.png')
print(out/'comparisons_frame.png')
