"""Apply already-confirmed owner numbering policy; preserve initial screen evidence."""
import json
from pathlib import Path
import pandas as pd
import nbformat
from scripts import benchmark_warranty_models as b,compare_callback_candidates_v2 as c
from scripts.audit_model_outcome_sample import OUT,ROOT
from scripts.build_supervisor_model_review import execute,export_html

def main():
    cases=json.loads((OUT/'case_details_private.json').read_text());screen=pd.read_csv(OUT/'sample_findings.csv')
    facts=pd.read_json(ROOT/'outputs/model_validation/20261016_target_research/archived_facts_private.json');facts.event_date_local=pd.to_datetime(facts.event_date_local)
    f=c.prepare_input(b.load_dataset_input(ROOT/'outputs/cp2-v2/source_refresh_20260927/refreshed/dataset_input.json'))
    rows=[]
    for case in cases:
        sale=case['sales_record_id'];anchor=pd.Timestamp(case['anchor_date'])
        feature=f[(f.sales_record_id==sale)&f.anchor_date.eq(anchor)];assert len(feature)==1
        feature=feature.iloc[0];events=case['following_events'];positive=[e for e in events if e['candidate_return']]
        finals=facts[(facts.sales_record_id==sale)&facts.session_total.eq(3)&facts.session_current.eq(3)&~facts.warranty_claim_candidate.eq(True)&facts.event_category.eq('service')].event_date_local.unique()
        if not positive:verdict='Consistent with no recorded return';reason='No candidate or explicit return event in the archived 30-day window; unrecorded returns remain unknown.'
        elif all(e['evidence']=='beyond_paid_sequence_needs_review' for e in positive) and feature.premise_type=='RESIDENTIAL' and feature.package_sessions_recorded==3 and len(finals)==1 and all(0<(pd.Timestamp(e['date'])-pd.Timestamp(finals[0])).days<=30 for e in positive):
            verdict='Supported warranty booking under owner rule';reason='Owner confirmed 4/3 and later visits are warranty visits; one unambiguous third paid service and all returns within its 30-day window.'
        elif all(e['evidence']=='free_visit_needs_review' for e in positive):
            verdict='Complimentary return; formal warranty not established';reason='Recorded additional visit supports the broader return target. Complimentary wording does not establish warranty entitlement.'
        else:verdict='Unresolved purpose or policy';reason='Insufficient evidence to apply the already-confirmed rule safely.'
        rows.append({'Case':case['case'],'Model result':screen.set_index('Case').loc[case['case'],'Model result'],'Premise':feature.premise_type,'Package services':int(feature.package_sessions_recorded),'Final finding':verdict,'Reason':reason})
    adjudicated=pd.DataFrame(rows);adjudicated.to_csv(OUT/'owner_rule_adjudication.csv',index=False)
    summary=adjudicated.groupby('Final finding').size().reset_index(name='Cases')
    nb=nbformat.read(OUT/'Outcome_Label_Audit.ipynb',4)
    nb.cells[0].source='# Outcome label audit: final findings\n\nThe first automatic screen conservatively flagged sequence-only visits. Applying the owner’s existing confirmation that 4/3 and later visits are warranty bookings resolves those cases when the residential 3x programme and 30-day window also agree. The initial screen remains preserved for audit.'
    nb.cells[1].source='import pandas as pd\nfrom io import StringIO\n'+f'display(pd.read_json(StringIO({summary.to_json(orient="records")!r})))'
    nb.cells[2].source='## Final case findings\n\nTen cases were selected from each prediction category (TP, FN, FP and TN), using deterministic ordering. Model correctness here is relative to archived recorded outcomes. A booking is not proof of delivered treatment or biological recurrence.'
    nb.cells[3].source=f'display(pd.read_json(StringIO({adjudicated.to_json(orient="records")!r})))'
    nb.cells[4].source='## Verdict and next steps\n\nNo definite label error was established in this 40-window source audit. Most positive cases agree with the owner’s numbering and coverage rules. One complimentary return remains distinct from formal warranty entitlement. Negative cases mean no recorded return in this archive, not proof that no problem occurred.\n\nKeep the broader recorded-return outcome distinct from a formal warranty claim. Do not silently relabel the frozen historical model or rewrite prospective prediction receipts. The 40 stratified cases cannot establish population label accuracy.\n\nNext: finish the prospective evaluation after outcomes mature, keep experimental model results clearly labelled, and complete the management tools and demonstration. Stronger treatment notes and location precision are future data improvements.\n\nOriginal automatic flags, private evidence and query receipts remain in this folder. Native Jupyter kernel unavailable; notebook cells executed sequentially in Python.'
    execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Outcome_Label_Audit.ipynb');export_html(nb,OUT/'Outcome_Label_Audit.html')
    (OUT/'adjudication_summary.json').write_text(json.dumps({'rule_source':'User confirmations in CP2 chat: 4/3 is warranty; residential 3x coverage 30 days after actual third service regardless of rescheduling length.','initial_screen_preserved':True,'sample':len(rows),'counts':dict(zip(summary['Final finding'],summary.Cases.astype(int))),'no_label_or_model_changes':True},indent=2))
    print(summary.to_string(index=False))

if __name__=='__main__':main()
