# Check-in pilot protocol (checkin_pilot_v1)

Declared 4 November 2026, before any pilot call. Configuration: `webapp/models/checkin_pilot_v1.json`, SHA-256 `84921e56b8f35e9fcd7dbe20b341b389e2505482e80313c5672799a717ce32a1`. Do not edit the configuration after 9 November; a change needs a new pilot id.

## Question

When the weekly check-in plan is used, do staff reach the customers most likely to need a return visit, what do the calls find, and do called customers make fewer customer-initiated return requests than comparable customers who were not called?

## Who is in the pilot

- Paid services recorded between 26 October and 13 November 2026 (so their check-in days 10 to 20 fall between 10 and 23 November).
- Return-visit risk score (return_risk_v1) of at least 0.12 at scoring time. This is roughly the top 15% of open services, mainly final services of residential programmes.

## Assignment

Each eligible service gets a fixed arm from a hash of its check-in key: `int(sha256("checkin_pilot_v1|" + key)[:8], 16) % 2`; 0 is **call**, 1 is **comparison**. The assignment does not depend on staff choice, the score or the customer, and it can be reproduced later.

- Call arm: shown in the weekly plan with a "pilot" label. Staff call or message around day 10 and record the result.
- Comparison arm: hidden from the plan from 10 to 23 November. Staff do not contact them unless the customer gets in touch; normal service continues.
- Services below 0.12 are not part of the pilot and appear in the plan as usual.

## Recorded for each call

Result (spoke, no issue / issue found, advice given / return visit booked / no answer), optional note, call minutes, day of the 30-day window, score at the time and pilot arm. All are saved in the internal action ledger; source sheets and Calendar are not changed.

## Measures

Process measures, available by 24 November:

1. Check-ins recorded, customers reached, and the share of planned pilot calls completed.
2. Share of reached customers with an issue, and return visits booked early.
3. Average call minutes.
4. Comparison customers contacted by mistake (should be zero).

Outcome measures, available from 14 December (30 days after the last pilot service):

5. Customer-initiated return rate by arm. A recorded return for a service whose check-in booked a visit counts as **staff-booked**, not customer-initiated, because calling customers creates bookings that would otherwise look like returns.
6. Any recorded return by arm, and expected returns from the score, as context.

Run: `python scripts/evaluate_checkin_pilot.py --ledger <ledger> [--labels <matured labels> --as-of <date>]`.

## Expected size and how to report it

About 20 to 30 eligible services and about 5 expected returns in total. This is a feasibility pilot: report counts and rates per arm with the sample size; do not claim a statistically significant effect. The final report (deadline 30 November) reports the process measures; the outcome comparison is reported as declared and still maturing.

## Owner agreement needed

Before 10 November the owner agrees that (a) staff will call the pilot customers shown in the plan and record the result, and (b) the comparison customers will not be proactively contacted for these two weeks. If the owner prefers that every high-risk customer is called, set the pilot aside: record process measures only and state that no comparison group was kept.

## Unchanged

The frozen pest-return experiment, its collector, ledger and 30 November evaluation, and the return_risk_v1 model.

## Decision, 5 November 2026: pilot not run

The owner declined the pilot before any pilot call. No comparison group is kept and `CP2_CHECKIN_PILOT_APPROVED` stays unset, so the portal shows the normal weekly check-in plan to everyone (highest chance first) and no customer is held back. The configuration file and its hash are unchanged and unused.

Report it as: a randomised check-in pilot was designed and declared, but not run at the owner's request, so there is no evidence on whether calls reduce returns. Check-ins that staff record in normal use can still be counted as process measures (calls made, issues found, visits booked) with `scripts/evaluate_checkin_pilot.py`, labelled as routine use, not a pilot.
