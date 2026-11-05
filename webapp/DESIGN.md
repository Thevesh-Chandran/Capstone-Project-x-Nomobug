# Interface design

The website uses a compact record-oriented layout inspired by [GitHub Primer](https://primer.style/product/) and [Zoho CRM's list/detail workflow](https://www.zoho.com/crm/resources/guided-tour/zoho-crm-overview.html).

## Overhaul: 2 November 2026 (second pass)

The first redesign still read as generated: an oversized cobalt hero, scores out of 100, weight sliders, seven option cards and a nine-item action plan on the landing page, a marketing pitch on the sign-in page and expanded display type everywhere. The second pass rebuilt both the look and the content as a quiet working tool.

- **Look (third pass, owner feedback that it looked like a static old website):** black, white and light blue as a modern product. Black sidebar with the original wordmark and a light blue active pill; each main page opens with a black header band (greeting or title, short lead, four stat tiles with light blue sparklines and progress rings); content sits on white rounded cards (14px) with soft shadows on a pale cool-grey canvas (`#F3F6FA`, not a blue wash). Light blue (`#8CC4FF`, `#4C9BF5`, `#E1EFFE`) is used for data, chips, avatars, bars and the active state; buttons are black pills. Lists use initials avatars, due-date chips and risk rings; cards fade up on load and bars grow in (disabled under reduced motion). The sign-in page pairs a black panel with a light blue radius motif (from the map tools) with a white form.
- **Merged with the feature review (2 November, evening):** the menu follows the development workspace: Today, Follow-ups, Booking calendar, Sales & return maps, Customer history; Reporting: Sales dashboard; Research (collapsed, opens automatically when one of its pages is active): Forecasts & model evidence, Warranty-risk research. Today shows only source-backed work (payment reminders, next-week bookings, contracts missing reminder dates) plus three quick-action tiles; experimental scores, upsell lists and speculative suggestions stay off it. Unconfirmed owner targets read "Not set" and are not scored. The remaining assistant-style features were removed from the interface: the "What needs checking?" / "Explain payment follow-ups" buttons on Follow-ups and the "Discuss it with the team" brief and "Explain the next decision" panel on the booking calendar. Server endpoints were left unchanged.
- **Sign-in:** a small centred form with the wordmark. No pitch copy.
- **Navigation (built by `static/shell.js`, shared with the heatmap page):** Today, Follow-ups, Payments, Scheduling, Customers, Warranty risk; Reports: Performance, Sales dashboard, Areas, Heatmaps; Models: Forecasts and models, Accuracy by district. Sign out and the snapshot date sit at the foot of the sidebar; there is no top bar.
- **Today** (`#today`, landing page; `#decisions` redirects here): four figures (sales last 30 days, hours booked next week against the forecast, bookings forecast, open balances), then the work for the day as plain lists: payment reminders due this week, properties to check in with after a recent service (warranty-risk model), first-time customers to offer a maintenance package (repeat-purchase ranking). The side column shows next week's booked hours against the forecast, the three remaining suggested actions in plain language, and contracts missing a reminder date.
- **Performance:** one sentence summary, a measures table (now, target, compared with, status), monthly sales against expected, booking forecast error against a simple average, and contract collection as a single bar. Unconfirmed owner targets are flagged "to confirm with owner".
- **Warranty risk:** a one-sentence summary, four figures, the property table with the window end date, and the model evidence in a collapsed "How reliable is this list?" section.

Option and measure wording in `webapp/analytics.py` was rewritten in plain language (no approximately signs, "YoY", "WAPE" or "naive baseline" on screen).

## Shared rules

- Light blue canvas, white cards, black sidebar and primary buttons; blue for links and data.
- Instrument Sans, 4/6/8px radii, 32px controls. Motion is minimal and disabled under reduced-motion.
- No em dashes, middle dots or arrow glyphs in interface text.
- Official Nomobug wordmark, shown as supplied (black). Third-party brand assets are not copied.
- One navigation, built once in `shell.js`, used by the workspace and the map page.
- Lists and tables carry the work; explanations go in collapsed details or tooltips, not banners.
- Status colours convey status only. Charts and maps keep their data colours.

## Workflows

### Decision flow - 30 October 2026

Plan now opens a booking/rescheduling workspace, with Weekly demand as its second tab. The appointment picker searches recognised customer appointments; breaks, meetings and availability blocks cannot be selected for removal. All noncancelled blocks remain constraints. Only the one explicitly selected appointment is omitted from a hypothetical reschedule calculation. No Calendar mutation occurs.

The booking tool reads an independent, private six-Calendar extraction with its own source hash and capture time. It rejects missing, incomplete, invalid or older-than-36-hour schedules. A daily reporting attempt exports this verified schedule before unrelated financial/programme reconciliation, without marking Gold as published. The previous good schedule is retained on failure and expires by its own timestamp.

Staff must supply the date, duration, working hours, travel allowance and checked teams. Coverage is a preference; alternatives are tagged usual area, cross-area cover or backup. Sales is consultation-only, Beast inactive, and Replacement limited to confirmed KL/Selangor coverage. Results are Calendar-fit options, not verified travel feasibility, confirmed availability or trained predictions. Working hours, breaks and service suitability require a staff confirmation. The first version does not estimate road times or claim travel savings.

Implementation: `booking.py` validates and checks the source intervals; `static/booking.js` supplies the search and option comparison; `config/cp2_team_coverage.json` is the single team/area registry. Private snapshot delivery uses the existing restricted storage and IAP APIs.

Primary navigation is Work, Plan, Customers & areas, Dashboard and Evidence. Customer records and maps share contextual tabs. Existing deep links remain valid; the Looker report itself is unchanged.

Plan begins with the next decision, not an experiment list. Its summary distinguishes stale sources, a missing exact-week hours forecast, missing capacity assumptions, a scenario shortfall and demand within the saved scenario. Expected hours and available hours appear together; the comparison updates as staff enter a scenario and marks unsaved changes. Saving retains the existing private, concurrency-protected ledger. Downloaded briefs include the saved decision, assumptions, source release and booking concentrations.

The heatmap counts upcoming days only. The most-booked days are source observations, never evidence of an overloaded team. Neither team/day demand predictions nor automated roster changes are provided. The one-week hours estimate and two-week booking estimate retain their separate horizons. Source freshness blocks a capacity recommendation, and no historical test chart substitutes for a missing live forecast.

Task-focused assistant requests for payment follow-ups and weekly planning use verified workspace briefs directly. The plan brief uses saved capacity when available and explicitly separates the two-week booking estimate from one-week hours. Broader Ollama answers retain their existing evidence and limitations.

This change does not establish business adoption or improved model accuracy. Management still needs to confirm whether the planning comparison is useful in its own workflow.

- Operations opens the complete follow-up worklist. Counts, tabs, customer search, exact balances and recorded review progress remain source-backed. Review opens the existing drawer; names also open it. Staff checklists are collapsed initially.
- Customers shows labelled columns for customer, recorded sales, programme count and relationship. Expanding a customer retains purchases, programme links and contract details.
- Weekly planner retains the team/day booking heatmap, separate forecast horizons and staff-entered capacity inputs.
- Area explorer retains geographic filters, zoom, density colours and source coverage. Its navigation and controls share the main application style.
- Model evidence keeps experimental limitations and separates historical metrics from saved future forecasts. Design changes do not change model results.
- Assistant task buttons and source links remain functional. This redesign does not claim to solve every open-ended AI question or change Ollama inference speed.

## Implementation

`static/crm.css` is the shared final application theme loaded after the existing component sheets. `static/workspace.js` builds the follow-up table and review drawer. `static/app.js` renders customer details. `static/index.html` and `static/maps.html` share labels and SVG navigation icons. The server serves the new stylesheet using the same static-asset path rules.

Data definitions, private access, model weights, source refresh jobs and payment records are outside the scope of these presentation changes. The Looker Studio report is separate and was not edited.
