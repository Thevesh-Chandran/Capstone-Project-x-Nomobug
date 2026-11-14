> Review note, 12 November: this is a dated talk track, not the current operating policy. See CP2_PROJECT_REVIEW_20261112.md for corrected claims. Staff follow up with all customers; recorded returns are not automatically free warranty claims.

# Presentation story: problem, decision, model, proof

A talk track for the CP2 presentation. One problem runs through it; every part of the system appears only where it serves that problem.

## 1. The problem (1 minute)

- Working part-time at Nomobug, I kept seeing jobs marked as done come back as complaints and return visits.
- The records confirm it: in the last 12 months about **18% of appointments, roughly 57 a month, were return visits** for work already done. Each one is unpaid team time, a disrupted schedule and a customer who trusts us less.
- Management could sense where problems came from but could not prove it: sales, bookings, warranty visits and payments sat in separate Sheets tabs and six Calendars.

## 2. What I built to see the problem (1 minute)

- A checked pipeline: Sheets and Calendar, immutable snapshots, BigQuery, tests and reconciliation, then the dashboard and the staff portal.
- This is the foundation, not the headline. It is what makes it possible to link every return visit to the sale and service it came from.

## 3. What the data showed (1 minute)

- Returns are not random. After the **first service of a programme only 2%** come back. After the **final service of a residential programme, 20%** do, because that is when the 30-day warranty window opens and the customer is judging the result.
- Earlier returns at the same address or in the same programme roughly double the odds again.
- Weather and area, which the proposal expected to matter, did not improve the predictions. That is a finding in itself.

## 4. The model (2 minutes)

- **Return-visit risk score:** for every paid service, the chance that the same customer needs a return visit within 30 days.
- A logistic regression on 13 inputs known before the visit (programme position, premise, package, earlier returns, gap since the last service, pest group). It is chosen because it is explainable: each factor has a clear multiplier staff can understand, and it beat a 90-input random forest anyway.
- Built properly: inputs and settings chosen on November 2025 to March 2026 only, model frozen, then assessed on May to October 2026, held out from this model fitting, with 30-day gaps and no sale in two periods.

## 5. Proof (2 minutes): the one chart to show

"If staff can check only 1 in 5 services, how many future returns do they reach?"

| Approach | Returns caught by checking 20% of services |
|---|---:|
| Random | 21% |
| Simple rule (final residential service) | 52% |
| **Return-risk score** | **62%** (78% at 30%) |

- AUC 0.81 (95% range 0.77 to 0.85) on 1,270 services and 108 returns.
- Why not "accuracy": predicting "no return" every time is already 91% accurate and catches nothing. The question that matters is how many returns the team can reach with limited effort.
- Calibration remains limited: the top fifth predicted 21% and recorded 26%. It undercounted total returns by about 17%, so predicted totals must not be used as a reliable staffing forecast.

## 6. How Nomobug uses it (1 minute)

1. **Before the visit:** high-risk jobs on tomorrow's schedule get a note for the technician (extra time, check harbourage areas, clear aftercare advice).
2. **Day 10 check-in:** a short call or WhatsApp to the highest-risk customers, before most return calls arrive (most calls come in the third and fourth week).
3. **Capacity:** the sum of the chances is the expected number of return visits, so the booking calendar keeps room for them.

The other portal tools support these actions: Follow-ups for the check-ins, the Booking calendar for capacity, the maps to see where returns cluster, and Customer history to look up a flagged customer.

## 7. Honest limits and next step (1 minute)

- A recorded return visit is not proof the pests came back.
- The score ranks risk; it has not yet been shown that early check-ins reduce returns. The next step is a small pilot: check in with half of the high-risk customers and compare return rates.
- The original frozen pest-return experiment is reported separately on 30 November.

## Likely questions

- *Why not the original frozen model?* Its only held-out test had 100 services and five returns, too few to judge, and it scored below the always-no-return baseline on accuracy. The new score was tested on 1,270 services and 108 returns, was chosen on a separate validation period, and is explainable. The frozen experiment is still reported on 30 November.
- *Isn't the rule almost as good?* The rule is a strong baseline, which is why it is shown. The score adds 10 percentage points at the same effort (95% range +2 to +17) and also ranks the services the rule ignores.
- *Could you get higher?* The random forest on every available input, including weather, flood and land-cover data, did not beat the simple score, and earlier studies of gradient boosting and pest-specific models found the same range. The limit is what the records capture (no treatment detail, no confirmed pest on the return visit), not the algorithm.

Evidence: `outputs/model_validation/20261103_return_risk/Summary.md`. Portal page: Return-visit risk.
