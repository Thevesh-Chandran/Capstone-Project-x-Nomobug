"""Monthly historical diagnostic; no training or original experiment writes."""

def main():
    import json
    from pathlib import Path
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from scripts.publish_return_risk_predictors import from_published_release, ROOT
    from webapp import return_risk, storage
    uri="gs://cp2-portal-profound-keel-500007-s4/current"
    from_published_release(uri)
    folder=next((ROOT/"outputs/return_risk_recovery").iterdir())
    raw=json.loads((folder/"return_risk_features/mature_labels/dataset_input.json").read_text())
    rows=[dict(zip(raw["columns"],r)) if isinstance(r,list) else r for r in raw["records"]]
    result=return_risk.monitor(rows,datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date())
    (folder/return_risk.MONITOR).write_text(json.dumps(result))
    storage.publish_business(uri,folder,name=return_risk.MONITOR)
    print("Monthly historical diagnostic published; frozen experiment unchanged")

if __name__ == "__main__":
    main()
