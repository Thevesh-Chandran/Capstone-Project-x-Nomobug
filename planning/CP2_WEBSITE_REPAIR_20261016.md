# Website repair and assistant latency check — 16 October 2026

Verified faults:
- Release 00031 omitted webapp/models/repeat90_v1.json. Planning requests failed with FileNotFoundError; restored the model to the source-only container package.
- Slow assistant requests and four-request Cloud Run concurrency produced platform 429s on ordinary customer/planning requests. Portal concurrency increased to 16, keeping one instance and one simultaneous AI-generation slot.
- Client now gives useful busy/session/unavailable messages when platform errors are HTML.
- Common area-performance suggestion now reads the saved district evaluation directly. Live answer visible within 277 ms including browser actions/state observation.
- Generated prompts omit unused registry contents, compact JSON and irrelevant warranty clauses. Generation ceiling reduced from 220 to 160 tokens; original evidence still attached after citation validation.
- Container smoke check now loads repeat-purchase model, beyond imports.
- Seven-day payment filter corrected to today through today + 6 days, inclusive.
- Dashboard frame switched from lazy to eager loading for explicit report navigation.

Verification:
33 focused Python tests passed. Real published source API acceptance passed: staff auth, spatial reconciliation, verified THAS 4+20 programme, no-match customer search, payment totals, area/date/radius totals, invalid dates and planning tools.
Live browser: customer CUST1412 found, repeat list rendered, upcoming payment filter returned 7 contracts, system/forecast rendered while AI generation was active; warranty map 350 located signals, historical model map 100 services, custom Petaling radius returned source-backed figures.
One generated explanation about sales vs bookings completed successfully; Cloud Run recorded 29.334 seconds. This is one observed latency, not a general speed guarantee. Earlier request logs included 88–159 seconds, on different questions. General generated answers remain slower than verified fact answers; no model-quality improvement claimed.
Build with workflow repairs: 73ee7c2a-e1b2-45ad-9df3-0699b47538a1; revision cp2-portal-00032-7mv.
Final embed/filter build: f07c4b0a-a9d3-425a-9b2c-32be8fd26a6d.
Frozen recurrence model, outcome protocol and source facts were not modified.

Final deployment: cp2-portal-00033-tsh, 100% traffic, container model smoke passed. Portal concurrency 16, max one instance retained.

Remaining verification limit: embedded Looker frame remains visually blank in controlled Chrome after eager loading. The same embed URL opens the report structure in a separate tab. No report sharing/configuration was changed; Open in Looker is available. Do not report embedded rendering as passed.
