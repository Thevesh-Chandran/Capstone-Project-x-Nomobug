# CP2 demonstration guide

Aim for 8–10 minutes. Use the private website while signed in. Keep customer names, contact details and private balances out of any public recording. The owner presents the Looker dashboard; its completion is a separate acceptance item.

## 1. Explain the business problem — 45 seconds

“Nomobug records sales, service bookings and payment reminders in separate sheets and calendars. The project connects those records, checks their consistency and gives management a dashboard plus private operational tools. It also evaluates whether a paid service will be followed by a recorded pest-related return within 30 days.”

Explain two definitions immediately: sales are recorded package prices, and bookings are not verified completed treatments.

## 2. Show the management dashboard — owner, 2 minutes

Use the finished Looker report to answer one concrete question each about sales, customers, team bookings and payment reminders. Demonstrate one date filter and reconcile one displayed total. Do not describe incomplete pages as finished or include private experimental risk scores.

## 3. Show customer lookup — 1 minute

Open Customers. Search by a reviewed sale ID, such as CUST1412, in the private demonstration. Expand its programme history. Explain that the confirmed 4-service and 20-service sales form one programme; an earlier separate purchase remains distinct. Then enter an impossible search string to show the no-match state.

The repeat-purchase priority list is a separate experimental tool. Say: “This ranks potential follow-up candidates. It is not a probability guarantee, and it does not send messages.” If showing its historical evidence, include both 13 buyers found and 99 false alerts in 112 reviews.

## 4. Show payment follow-up — 1 minute

Open Payment follow-up. Switch between all contracts, upcoming reminders and missing dates. Explain that paid and remaining figures come from Sales updates. A reminder date is a staff schedule; a green cell only means that date has passed. Do not call a past reminder unpaid, overdue or already sent. Show how unknown amounts remain unknown rather than becoming zero.

## 5. Show custom-area exploration — 1 minute

Open Area explorer. Set From and To dates, then compare the same centre at 5 km and 20 km. More records can enter the larger radius. Point out unlocated records and boundary uncertainty. This is exploration of recorded sales and bookings, not profit or biological pest prevalence.

If opening Model test by area, explicitly say it uses the historical 100-service test. Changing the district changes the evaluated subset, not the trained model. Small groups and groups without positive cases cannot establish useful detection performance.

## 6. Show explanations and limits — 1 minute

Ask the built-in residential 3x rescheduling question. Show its Verified evidence label and Warranty policy source. Ask whether a green reminder date proves payment. Then explain that these confirmed rules are direct answers, while broader explanation questions use private Ollama. A generated answer still needs source checking and may be slower.

## 7. Explain the models honestly — 1 minute

Use the separate larger historical assessment to explain the sample-size concern: 2,075 services and 184 positive windows, with precision 23.0%, recall 64.7% and F1 34.0%. Its training/calibration differs from the original 100-service test; do not present the two as a controlled comparison. Calendar notes yielded a small, inconsistent gain (pooled F1 31.5% to 32.9% on the same 2,172 validation services), with more missed returns. The 40-case source audit found no definite label error, but cannot establish population label accuracy. Staff already follow up all customers; top-20% ranking is not the main operational justification for this return model.

“The pest-return model predicts a recorded corrective return within 30 days. Its historical threshold accuracy was 94%, compared with 95% from always predicting no return on the same 100 services. Only five cases were positive. It captured four in the top 20 review list, but the evidence is too small to claim reliability.”

Show the weekly booking estimate as an experimental four-week average. Explain that an error in bookings is MAE, not classification accuracy. Do not call 13.5% WAPE ‘86.5% accuracy.’

## 8. Show deployment and the future test — 45 seconds

Show Model & system and the architecture in the report draft. Explain Docker packaging, daily checked releases and the separate cloud collector. The laptop is not required for production collection. Website availability does not prove that every prediction was captured.

“The original incomplete cohort is preserved. The separate recovery test covers services from 16–30 October. Its full 30-day outcomes are checked on 30 November. If completeness fails, the system reports that failure rather than fabricating an accuracy result.”

## Before presenting

- Recheck source dates, website access and the latest collector audit.
- Verify the owner's dashboard totals and filters against the same approved release.
- Keep private examples in a restricted live session; use anonymised examples in shared slides.
- Open the website and evidence documents before the presentation. Keep a dated, clearly labelled fallback screenshot in case network access fails.
- After 30 November, replace “pending” with the actual governed result or completeness rejection. Do not promise an accuracy percentage in advance.

## Likely supervisor questions

**Why continue with a model below the accuracy baseline?** The task is imbalanced, so accuracy alone can hide failure to detect returns. Ranking may help prioritisation, but the small positive sample means the project must report false alerts and uncertainty. It is an experimental component within a wider checked information system.

**Why not run prediction entirely in BigQuery once a day?** BigQuery stores and derives data, but the declared experiment requires timely source refresh and immutable predictions near the service capture time. The separate collector coordinates that work; the daily reporting job serves a different purpose.

**Does rainfall cause more pest returns?** The current observational data can show associations, not establish causality.

**What is finished before future outcomes mature?** The pipeline, website tools, Docker deployment, historical research and demonstration can be verified now. Future performance must wait for complete outcomes and coverage checks.

## Live map walkthrough — 16 October release

Open Area explorer → Open hotspot & sales maps. Start with Customer sales and Density heatmap. Show the date controls, located customers/purchases and purchases without coordinates. Switch to Proximity groups, choose a group, then Zoom into this group. Click a purchase marker and Open customer history. Return to maps, select Warranty visit signals, and explain that these are Calendar signals rather than verified biological recurrence. Finally select Model performance: the top cards retain the full historical 100-service, five-positive evaluation; the map only contains 85 located test services, and insufficient area evidence stays grey. Changing area does not retrain the model. Reset must clear the old selection.
