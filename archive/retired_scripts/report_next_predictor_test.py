"""Plain-language, portable report for the completed paired development test."""
import json
import pandas as pd
import nbformat
from scripts.test_next_predictors import OUT
from scripts.build_supervisor_model_review import execute,export_html

def main():
    comparison=pd.read_csv(OUT/'comparison.csv');folds=pd.read_csv(OUT/'fold_metrics.csv')
    base=folds[folds.variant.eq('Existing inputs')]
    score=comparison[['Inputs tested','Precision','Recall','F1']].copy()
    for col in ['Precision','Recall','F1']:score[col]=(score[col]*100).round(1)
    score=score.rename(columns={'Precision':'Correct warnings (%)','Recall':'Returns detected (%)','F1':'F1 score (%)'})
    support=pd.DataFrame([
        ['Same-pest previous history',3620,'756 services have a previous fully observed matching window; others have zero history.'],
        ['Assigned team changed',1736,'Exact content/date match and snapshot timing check. Assigned team, not individual technician.'],
        ['Nearby mapped food places',204,'68 addresses; historical January maps. Location uncertainty up to 250m.']],
        columns=['New input','Known service rows (out of 3,620)','What this means'])
    technical=comparison[['Inputs tested','Average precision','Brier error','Periods improved on both']].round(4)
    md=nbformat.v4.new_markdown_cell;code=nbformat.v4.new_code_cell
    nb=nbformat.v4.new_notebook(cells=[
        md('# Did the three new inputs improve the model?\n\n**Not consistently enough to adopt them.** Combining all three improved the average F1 score, but reduced average precision and worsened probability error. The live frozen model is unchanged.'),
        md(f'## What we tested\n\nThe same Extra Trees model and original inputs, adding each candidate separately and then together. Three chronological development periods in April–December 2025 contain **{int(base.test_services.sum()):,} evaluated service windows and {int(base.test_returns.sum())} recorded return windows**. Each period trains and calibrates on earlier, purged data. The 2,075-service 2026 assessment was not used. These historical periods have been explored before; this is a development comparison, not new independent accuracy.'),
        code('import pandas as pd\nfrom io import StringIO\n'+f'display(pd.read_json(StringIO({score.to_json(orient="records")!r})))'),
        md('**Correct warnings** means the percentage of predicted returns that actually had a recorded return. **Returns detected** means the percentage of real returns caught. **F1** balances those two. Numbers above are averages of three period-level scores, not pooled results. A higher F1 alone does not establish a reliable improvement.'),
        md('## What data was available'),
        code(f'display(pd.read_json(StringIO({support.to_json(orient="records")!r})))'),
        md('Same-pest history counts fully matured earlier service windows for the same address and exact pest category, within 180 days. One return can label more than one earlier window, so these are not counts of distinct warranty claims.\n\nFood counts represent restaurant/cafe/fast-food/food-court **map points within 500m of the estimated location**. They omit businesses mapped as areas and do not prove whether a business was operating. January snapshots can be nearly a year old. Missing values stay unknown. All 68 eligible addresses returned both annual snapshots.'),
        md('## Why we are not replacing the model\n\nBefore testing, the rule was: average precision must increase and Brier error must decrease in every period. None passed. Higher average precision means better ranking of returns; lower Brier error means more accurate probabilities. No practical improvement was established.'),
        code(f'display(pd.read_json(StringIO({technical.to_json(orient="records")!r})))'),
        md('## What remains unresolved\n\n- Reliable infestation severity, treatment/product/dose, hygiene and building age are still unavailable historically.\n- Most locations are too approximate for this 500m food-place feature. Coverage improvements need source validation.\n- Historical snapshot timestamps are a conservative proxy for what was known, not a full change log. Prior outcomes assume availability after their observation window.\n- The original prospective experiment is unchanged. These results do not increase its accuracy or remove its sample-size limitations.\n\nThe first attempted food extraction returned HTTP 403. Its empty-feature comparison was rejected and preserved with DO_NOT_USE.md. This corrected run used the working count endpoint and excluded constant/empty new inputs from each fit.\n\n[ohsome API documentation](https://docs.ohsome.org/ohsome-api/development/endpoints.html). © OpenStreetMap contributors. Seven targeted tests passed; original frozen-file hashes are unchanged. Notebook cells executed in order in Python and validated with nbformat; a native Jupyter kernel was unavailable.')])
    nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
    for cell in nb.cells:
        if cell.cell_type=='code':cell.metadata['jupyter']={'source_hidden':True}
    execute(nb);nbformat.validate(nb)
    nbformat.write(nb,OUT/'New_Inputs_Test.ipynb');export_html(nb,OUT/'New_Inputs_Test.html')
    print('Executed and saved notebook and HTML.')

if __name__=='__main__':main()
