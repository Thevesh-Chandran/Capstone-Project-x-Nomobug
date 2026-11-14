# CP2 project review

Reviewed 12 November 2026, Malaysia time.

## What this repo does

The system connects Nomobug's sales and Calendar records to management reporting, customer follow-up, payment reminders, booking support and experimental prediction models. It serves a small internal team; this review assumes that workload, not a public high-volume service.

The project is on a defensible track as a decision-support system. Its strongest evidence is the checked data pipeline, historical model comparisons and working operational tools. It has not established that using the scores reduces pest returns, saves staff time or increases sales. Those are separate business-outcome questions.

## Evidence checked

- Current README, system record, project guide, deployment files, research implementation and saved return-ranking selection/results.
- Text from the latest final report: `docs/2 Final Report/Final Report CP2 Thevesh Chandran 24017717 Updated 20261108.docx`.
- Text from all 15 slides of `docs/4 Presentation/Nomobug Final Presentation.pptx`.
- Website model rendering, report integration, authentication paths and relevant tests.
- Live model page: authenticated access, populated embedded charts and a 12 November source snapshot.
- Latest reporting execution `cp2-reporting-daily-zcf5q`: succeeded, completed 12 November 06:10 MYT.
- Scheduled dashboard execution `cp2-dashboard-refresh-9w6n4` completed at 06:47 MYT. Release refresh `cp2-dashboard-refresh-v94ht` also succeeded. The live bookings page displays “Forecast ± typical error”.
- Full Python suite: 776 passed, 20 warnings. JavaScript syntax and the existing work-queue interaction check passed.

These checks do not establish that every source record is correct. Warehouse reconciliation was not rerun during this review. Report and slide text was extracted; their complete rendered layouts were not visually revalidated.

## Must fix before presentation

### 1. Keep returns separate from warranty claims

**Problem:** slide 2 says every return is a free trip; slide 3 calls the model outcome a warranty return. The label is a recorded pest-related return signal. Commercial clients have no warranty; paid repeats, scheduled programme visits and genuine claims are different events.

**Correction:** use “recorded pest-related return within 30 days” for the prediction target. Explain warranty eligibility separately. Do not infer a free visit or financial loss from the model label alone.

**Affected:** slides 2–3, opening of the project guide and parts of the presentation story. Existing historical records remain unchanged.

### 2. Remove the unverified staff-capacity premise

**Problem:** the report abstract, slide 7 and slide 12 frame the main value as selecting only some customers to call. The owner's stated practice is to follow up with everyone.

**Correction:** describe the score as extra context for reviewing service history and recognising higher-risk cases during normal follow-up. The top-20% comparison is a benchmark showing ranking concentration; it is not the company's contact policy. Do not claim time saved from that comparison.

**Implemented:** clarified the website benchmark wording and project guide. The Word report and PowerPoint need the wording changes listed below.

### 3. Qualify the historical assessment

**Problem:** “tested once on services the model never saw” can be read as an untouched final test for the whole project. The script excludes those rows from this model's fitting, but later-2026 historical periods have already been explored in earlier project experiments.

**Correction:** “Historical assessment on 1,270 later services held out from this model fitting.” Validation selection and chronological separation are real protections; they do not erase repeated research on the same period.

**Implemented:** corrected the project guide and annotated the old talk track. Do not relabel this assessment as prospective.

### 4. Correct weather preprocessing before using its comparison as evidence

**Problem:** `scripts/research_return_risk_20261103.py`, function `feats`, fills missing rain and humidity using medians from the full dataset before partitioning. Validation and test feature distributions therefore affect those candidate inputs.

**Impact:** the selected S5 model has 13 structure/history/pest inputs and excludes both weather columns. Its direct inputs do not use these medians. However, weather-candidate validation comparisons were not fully isolated; the selection comparison should be rerun with training-only preprocessing before claiming that these candidates were properly ruled out.

**Repaired and rerun:** missing-weather replacements now fit on development rows for validation and development plus validation for assessment. Separate evidence: `outputs/model_validation/20261112_weather_preprocessing/`. It selected the same S5 model and C=0.03. Features, scaling, intercept and source hash match; the largest coefficient difference is 3.4e-15 (floating-point rounding). Historical ROC AUC remains 0.811, average precision 0.277 and top-fifth capture 62%. This fixes the comparison procedure, not model accuracy. It is not a new independent test. Original outputs and production/frozen bundles were not changed.

## Further system finding

The Gold reporting publish checks and the static dashboard upload are different mechanisms. `dashboard/refresh/upload.mjs` uploads assets, then HTML, then deletes older assets. It is not an atomic whole-site release: an interrupted upload can leave mixed dashboard files, and deleting previous hashed assets can break an already-open browser tab. It also does not check deletion HTTP responses before counting removals.

The reporting pipeline's last-good-Gold guarantee must not be described as an equivalent guarantee for dashboard files. A future dashboard publishing change should use versioned directories and an atomic active-release pointer, retain rollback assets, and test an interrupted publish before replacing this mechanism. No warehouse data or old dashboard assets were manually deleted in this review.

## Model measures and their meaning

| Assessment | Evidence | What is supported | What is not supported |
|---|---|---|---|
| Current return-risk logistic model | 13 inputs; 1,270 services, 108 returns; ROC AUC about 0.81, sale-group bootstrap interval about 0.77–0.85 | Historical ranking discrimination | 81% classification accuracy, proven prevention or reliably calibrated individual probabilities |
| Ranking concentration | Top fifth contains about 62% of returns; simple rule about 52%, random order about 21% | Comparison at equal review size | A requirement to ignore other customers or evidence that calls prevent returns |
| Original frozen ExtraTrees holdout | 100 services, 5 returns; accuracy 94%, precision 40%, recall 40%, F1 40%; ROC AUC 0.891 | Separate historical assessment at its saved threshold | Strong reliability from only five positive cases; replacement of the current ranking result |
| Original majority baseline | 95% accuracy, zero returns detected | Why accuracy alone is inadequate | Proof that detecting returns is useless |
| Two-week booking forecast | MAE 12.76 bookings versus 20.73 baseline; 13 overlapping forecast dates | Historical error in booking units | 38% classification accuracy improvement or 13 independent trials |
| Next-week appointment hours | MAE 8.97 hours versus 11.77 baseline; 14 dates | Historical error in scheduled hours | Actual technician labour measured on site or a guaranteed staffing requirement |

The booking error reduction is about 38%; the hours error reduction is about 24%. Those are relative reductions in MAE, not accuracy percentages. Overlapping forecast windows share outcomes, so sample size should not be presented as independent evidence.

## Calibration, significance and geography

The highest risk band averaged about 21.3% predicted versus 26.4% recorded. Total expected returns were about 17% below recorded returns. Ranking quality and probability calibration are different: a useful order does not mean that a 20% estimate is an exact individual probability.

Logistic odds multipliers describe fitted associations. They are not causal effects, percentage-point changes or statistical significance tests. No p-values or confidence intervals for individual coefficients were established in the reviewed evidence. Correlated inputs and regularisation also affect interpretation.

The original 100-service map is a subset of that historical holdout, not all company services. Changing radius changes which records are summarised; it does not train a better model. Small local groups, especially those with few or no returns, cannot support reliable area accuracy claims. Do not choose the best-looking radius and present it as independent evidence.

## Report corrections

The latest report already explains many important limitations, including the five-positive holdout, underprediction, no measured intervention benefit and conditional future evaluation. Preserve those parts.

| Location | Change |
|---|---|
| Abstract, first model paragraph | Replace “when time is limited” with the owner's actual all-customer follow-up workflow. |
| Abstract and ranking results | Replace “tested once” with historical assessment held out from this model fitting; acknowledge prior exploration of the period. |
| Earlier forecast discussion | Specify “earlier weekly volume experiments” when saying no model beat the baseline. Later two-week bookings and next-week hours did beat their historical baselines. |
| Predictor methods | Add the full-dataset weather-imputation limitation and distinguish the selected non-weather model from the candidates. |
| Conclusions | State that operational functions are implemented, while business impact and prospective model reliability are not established. |
| System figures | Use the current Evidence dashboard and protected Cloud Run website; retain Looker/Ollama only in dated development history. |
| Final evaluation dates | Keep 30 November conditional on complete outcome and prediction coverage checks. A date alone cannot make missed predictions valid. |

Do not update the old PDF by renaming it. It is dated 6 November and is not the PDF version of the 8 November Word report. Export a new PDF after the report is revised and checked.

## Slide-by-slide review

| Slide | Required correction or status |
|---|---|
| 1 | The prevention-themed opening is a research question, not a demonstrated outcome. Explain that distinction when presenting. |
| 2 | Replace “Every return visit is a free trip back” with “Some return visits require another appointment”. Keep the residential warranty example explicitly illustrative. |
| 3 | Replace “homes” with “services” where the denominator includes commercial records. Replace “warranty return” with “recorded pest-related return”. |
| 4 | 06:45 is the scheduled dashboard start, not guaranteed completion. Today's successful build completed at 06:47. |
| 5 | Explain whether 222 means build nodes, tests or combined steps. Do not call it 222 tests unless the saved run establishes that count. Keep the separate 16 reconciliation checks. |
| 6 | Keep both 94% and the 95% baseline. Add 100 services / 5 returns and recall 40% so judges can assess the trade-off. |
| 7 | Label top-20% as an assessment benchmark. Use services, not homes. Remove the claim of a wholly untouched project test. |
| 8 | Rename “What makes a home call back” to “Inputs associated with recorded returns”. Keep the association-not-causation note and odds interpretation. |
| 9 | Label this “Earlier experiments”. Distinguish weekly volume forecasts from the newer models on slide 10. Weather findings need the preprocessing caveat. |
| 10 | Keep the MAE comparisons, add 13 overlapping booking dates / 14 hours dates and historical assessment. Scheduled hours are not actual labour. |
| 11 | Implemented workflow is a valid demonstration. Show the latest interface and source date. |
| 12 | Replace compulsory call selection with routine follow-up supported by service history and risk context. Day-10 calls are a proposed workflow, not proven prevention. |
| 13 | Public/aggregate summaries and protected individual drill-through are different. Verify the precise map view before claiming maps never expose addresses. |
| 14 | Good limitations slide. Future tests and any staff trial are conditional, not completed or guaranteed. |
| 15 | Close on integrated records, assessed estimates and recorded staff actions. Do not imply 6 of 9 returns were prevented. |

## Interface changes made in this review

- Removed the generic paragraph under “Prediction models” and the numbered question headings.
- Shortened each model's estimate and assessment text; kept the population and historical/future distinction.
- Moved detailed operating instructions into “Use and limitations”.
- Replaced generic “Take action” subtitles with direct section names: Customer follow-up, Payment reminders, Booking calendar and Customer history.
- Renamed “Treatment difficulty” and “Package fit” charts to measured return-share descriptions. Observed proportions do not establish treatment difficulty or suitability.
- Removed the implication that top-fifth precision establishes staff time savings.

The portal revision cp2-portal-review-1112 is serving all production traffic. At a 360-pixel browser viewport, Overview, Service follow-up, Payments, Bookings & workload, Sales & customers, Maps & patterns, and Prediction models had no document-level horizontal overflow. The Overview breadcrumb and model panels were checked in the browser. This pass covered page layout and model disclosure controls. Other mobile interactions still need separate checks.

## Tools and design assets

Hallmark, Ponytail audit/review tools, Agent Reach and Skill Inspector are installed locally. Evidence.dev dependencies are declared in `dashboard/package.json`; the live embedded charts are Evidence charts. Browser control is connected. Hallmark was not run as a wholesale redesign because the project-specific instruction preserves the ongoing existing design unless explicitly requested.

No third-party skill or MCP code was installed or updated in this review. Installation presence is not a security certification. New installation or updates require the configured static scan and source review. FreeLLMAPI is not needed for this project because the generative assistant was removed at the owner's request.

## Submission status

- Revised Word report and 15-slide PowerPoint are in their original document folders, with matching PDF exports. Corrected text was verified in both PDFs. PowerPoint text boxes flagged for overflow were adjusted and rechecked. Reviewed rendered previews of all 93 report pages and all 15 slides. Shortened the slide 8 heading to clear the overlap and replaced the outdated screenshots on slide 11 with a live demo link. Re-exported the slide PDF and inspected both revised slides.
- Model Performance is live and groups all six models and studies on one page. At 360 pixels, the live portal passed checks for customer search, follow-up filtering, map layer changes, zoom, area size, reset, and district selection. This was a targeted check of those controls.
- Source-to-Gold reconciliation passed all 16 checks for published release 20261111220025f8bd31 on 12 November. The audit receipt is outputs/project_audit/20261112_submission/kpi/summary.json. Checks apply to the pinned release and retain the documented business caveats.
- Verified that the 27 November evaluations at 12:00 and 13:00 MYT and the 30 November evaluations at 14:00 and 15:00 MYT are enabled. The last 30 November outcome window closes on 29 November. The original October 10 cohort is documented as incomplete, and the recovery audit records missed eligible predictions. Report each cohort according to its coverage checks when the scheduled results are available.
- Staff usability and business impact require separate evaluation if management agrees to a trial. Historical model comparisons do not establish those outcomes.

## Verdict

Keep the integrated reporting, booking and follow-up workflow. Present the models as assessed decision support, with historical results and future-test status clearly separated. The revised presentation distinguishes historical ranking from routine follow-up with every customer. The corrected weather comparison confirms the same selected model.

Not checked: exhaustive line-by-line source audit, every warehouse row, full rendered report/deck layout, every authenticated feature on mobile, and a new independent model evaluation. No model weights, thresholds, prediction timestamps or missed-window records were changed.
