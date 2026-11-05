"""Summarize the declared target research without claiming fresh test performance."""
import json
from pathlib import Path

from scripts import benchmark_warranty_models as b


def main():
    base = b.ROOT/'outputs/model_validation'
    broad = json.loads((base/'20261016_target_research/results.json').read_text(encoding='utf-8'))
    three = json.loads((base/'20261016_target_research_3x/results.json').read_text(encoding='utf-8'))
    names = {'et10_leaf5':'Extra Trees','rf_depth6':'Random Forest',
             'lr_c1.0_plain':'Logistic regression','hist_depth3':'Gradient boosting'}
    lines = ['# Return-prediction alternatives — 17 October 2026','',
        'Completed the bounded historical search across 7/14/30/60-day outcomes, each-paid-service and final-paid-service targets, all/residential populations, four model families and four feature sets. Added the owner-requested residential 3x third-service supplement. This is adaptive historical research, not new prospective accuracy.','',
        f"Broad search: **{broad['fits']} fits and {broad['candidate_contracts']} supported candidate contracts**. Residential 3x supplement: **{three['fits']} fits and {three['candidate_contracts']} contracts**. Some targets/folds lacked sufficient positive outcomes and were skipped rather than assigned a misleading accuracy.",'',
        '## Source and validation','',
        'The experiment uses the pinned 5,598-row archived research epoch, with 7,647 matching Calendar service facts. All source identities and all original 30-day labels reconciled before alternate outcomes were built. The recorded complete observation date is 13 September 2026. A 60-day service window therefore ends by that date; later immature anchors are excluded. This is a different source epoch from the 5,695-row prospective refit, so totals are not interchangeable.','',
        'Labels are recorded corrective/warranty Calendar visits linked to the sale, strictly after the anchor and within the selected number of days. They are neither independently confirmed biological recurrence nor formal claim-sheet submissions. One recorded visit can contribute to several earlier service windows. Final-service targets require one recorded occurrence of each paid stage 1..N. This is evidence of recorded stages, not proof every scheduled treatment was completed.','',
        'Current corrected programme links, later source revisions, and historical cancellation/source limitations are not fully regenerated into the archived epoch. Results therefore identify possible candidates for a current-source rebuild, not deployment-ready replacements.','',
        '## Fair comparison','',
        'Four chronological outer periods were declared in advance. Within each, training and a later calibration portion are separated by a full outcome-maturity gap and connected property/package groups. The evaluation period follows both. Calibration adjusts probabilities and chooses the F1 cutoff only from earlier calibration labels. Every eligible evaluation service is classified; there is no top-20% capacity quota.','',
        'Candidates below are the highest pooled historical F1 among contracts with at least three usable folds, within each target/horizon/population. Choosing winners from these inspected outcomes creates selection optimism; a new future evaluation is required. Different targets have different prevalence and business meanings, so the table is not a universal ranking of horizons.','',
        '## Leading supported alternatives','',
        '| Days | Anchor | Clients | Model / features | Evaluated | Positive windows | Recall | Precision | F1 | Accuracy / no-return baseline |',
        '|---:|---|---|---|---:|---:|---:|---:|---:|---:|']
    selected = []
    for horizon in [7,14,30,60]:
        for target in ['each_paid_service','final_paid_service']:
            for population in ['all','residential']:
                pool = [r for r in broad['summary'] if r['horizon']==horizon and r['target']==target
                        and r['population']==population and r['folds']>=3]
                if not pool:
                    continue
                r=max(pool,key=lambda r:(r['pooled_f1'],r['mean_ap']))
                selected.append(r)
                lines.append(f"| {horizon} | {'Each service' if target=='each_paid_service' else 'Final paid service'} | {population} | {names[r['model']]} / {r['features']} | {r['services']} | {r['positive_windows']} | {r['pooled_recall']:.1%} | {r['pooled_precision']:.1%} | {r['pooled_f1']:.3f} | {r['pooled_accuracy']:.1%} / {r['always_no_return_accuracy']:.1%} |")
    lines += ['', '## Residential 3x after the third paid service','',
        'This is the requested specific warranty-follow-up population. The 30-day outcome matches the stated residential 3x claim window after the actual third paid visit; no 14-day completion rule is imposed. Other horizons are research sensitivity checks, not changes to customer warranty entitlement.','',
        '| Days | Model / features | Folds | Services | Returns caught | Missed | False alarms | Recall | Precision | Accuracy / baseline |',
        '|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    selected_three=[]
    for horizon in [7,14,30,60]:
        pool=[r for r in three['summary'] if r['horizon']==horizon and r['folds']>=3]
        if not pool:
            lines.append(f'| {horizon} | Insufficient supported folds | — | — | — | — | — | — | — | — |')
            continue
        r=max(pool,key=lambda r:(r['pooled_f1'],r['mean_ap']));selected_three.append(r)
        lines.append(f"| {horizon} | {names[r['model']]} / {r['features']} | {r['folds']} | {r['services']} | {r['TP']} | {r['FN']} | {r['FP']} | {r['pooled_recall']:.1%} | {r['pooled_precision']:.1%} | {r['pooled_accuracy']:.1%} / {r['always_no_return_accuracy']:.1%} |")
    thirty = next((r for r in selected_three if r['horizon']==30), None)
    if thirty:
        always_yes_f1 = 2*thirty['positive_windows']/(thirty['services']+thirty['positive_windows'])
        lines += ['',f"For the 3x/30-day target, the leading searched candidate's F1 is {thirty['pooled_f1']:.3f}. Predicting a return for every programme would already achieve F1 {always_yes_f1:.3f}; that baseline catches every positive but raises many false alarms. The searched candidate's mean probability error is {thirty['mean_brier']:.4f}, versus {thirty['mean_baseline_brier']:.4f} for the earlier-data prevalence baseline. This comparison prevents a high recall alone from being mistaken for strong prediction."]
    lines += ['', '## Interpretation and next step','',
        'A shorter horizon can increase no-return accuracy merely by making returns rarer. The 7-day service target has only 11 positive windows in the entire archived source and fails the declared fold-support rules. It is not evidence of excellent prediction.','',
        'Prefer a target that matches a real management decision. The residential 3x/30-day final-service target has the clearest connection to the stated warranty period. Its historical result must still be checked against a regenerated current-source dataset, linked upsell programmes and cancellation rules before any new candidate is frozen. Any eventual candidate needs its own declared prospective cohort. The current 30-day frozen model and all existing prediction receipts remain unchanged.','',
        'Eight focused horizon/split tests passed, including same-day exclusion, exact end-day inclusion, incomplete-window exclusion, and sale-specific return matching. Original source metadata still matched its archived pin after extraction. All frozen bundle file hashes were checked before and after both searches.','',
        'Protocol: `config/cp2_target_research_20261016.json`; supplement: `config/cp2_3x_final_target_research_20261017.json`. Full per-fold metrics and all contracts remain under `outputs/model_validation/20261016_target_research/` and `outputs/model_validation/20261016_target_research_3x/`. No private customer records are included in this report.']
    path=b.ROOT/'planning/CP2_TARGET_RESEARCH_20261017.md'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'broad_fits':broad['fits'],'supplement_fits':three['fits'],
        'leading_3x':selected_three,'report':str(path)},indent=2))


if __name__=='__main__':
    main()
