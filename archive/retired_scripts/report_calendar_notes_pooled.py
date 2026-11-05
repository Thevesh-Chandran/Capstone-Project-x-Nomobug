"""Add exact pooled confusion counts to the completed notes experiment report."""
import json
import numpy as np
import pandas as pd
import nbformat
from scripts.test_calendar_note_predictors import OUT
from scripts.build_supervisor_model_review import execute,export_html

def main():
    metrics=pd.read_csv(OUT/'fold_metrics.csv');rows=[]
    for variant,part in metrics.groupby('variant',sort=False):
        tp=np.rint(part.recall*part.positives).astype(int)
        assert np.allclose(tp/part.alert_rows,part.precision)
        total=int(part.rows.sum());positive=int(part.positives.sum());alert=int(part.alert_rows.sum());hit=int(tp.sum())
        fp=alert-hit;fn=positive-hit;tn=total-hit-fp-fn
        rows.append({'Model':variant,'Services':total,'Actual return windows':positive,'Correct warnings':hit,'False warnings':fp,'Missed returns':fn,'Correct no-return predictions':tn,'Precision (%)':round(100*hit/alert,1),'Recall (%)':round(100*hit/positive,1),'F1 (%)':round(200*hit/(2*hit+fp+fn),1),'Accuracy (%)':round(100*(hit+tn)/total,1)})
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'pooled_results.csv',index=False)
    nb=nbformat.read(OUT/'Calendar_Notes_Test.ipynb',4)
    if not any(c.cell_type=='markdown' and c.source.startswith('## All validation services combined') for c in nb.cells):
        nb.cells[1:1]=[nbformat.v4.new_markdown_cell('## All validation services combined\n\nThese pooled counts are easier to interpret than period averages. Thresholds differ by period because each was chosen from its earlier calibration data. This is a historical rolling evaluation, not one fixed deployed model. The period-average table below is retained for the consistency check.'),nbformat.v4.new_code_cell('import pandas as pd\nfrom io import StringIO\n'+f'display(pd.read_json(StringIO({frame.to_json(orient="records")!r})))')]
    for cell in nb.cells:
        if cell.cell_type=='code':cell.metadata['jupyter']={'source_hidden':True}
    execute(nb);nbformat.validate(nb);nbformat.write(nb,OUT/'Calendar_Notes_Test.ipynb');export_html(nb,OUT/'Calendar_Notes_Test.html')
    print(frame.to_string(index=False))

if __name__=='__main__':main()
