"""Upload hash-checked private collector artifacts to one restricted GCS bucket."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

from scripts.cp2_cloud_collector import ARTIFACTS, ROOT


def inventory():
    registry = json.loads((ROOT / "config/cp2_model_current.json").read_text(encoding="utf-8"))
    pin = json.loads((ROOT / "config/cp2_live_feature_contract.json").read_text(encoding="utf-8"))
    paths = ARTIFACTS | {f"dbt/target/compiled/nomobug/models/{name}"
                         for name in pin["compiled_query_hashes"]}
    manifest = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(paths)}
    pinned = json.loads((ROOT / "config/cp2_cloud_artifacts.json").read_text(encoding="utf-8"))
    if manifest != pinned:
        raise ValueError("Local cloud artifacts differ from committed immutable manifest")
    if manifest["outputs/cp2-v2/prospective_callback_v2/bundle.json"] != registry["bundle_sha256"]:
        raise ValueError("Frozen bundle hash differs from model registry")
    bundle = json.loads((ROOT / "outputs/cp2-v2/prospective_callback_v2/bundle.json").read_text())
    for model in bundle["models"].values():
        name = f"outputs/cp2-v2/prospective_callback_v2/{model['file']}"
        if manifest[name] != model["sha256"]:
            raise ValueError("Frozen model artifact hash mismatch")
    for name, digest in pin["compiled_query_hashes"].items():
        path = ROOT / "dbt/target/compiled/nomobug/models" / name
        if sha256(path.read_text(encoding="utf-8").encode()).hexdigest() != digest:
            raise ValueError("Compiled live SQL differs from frozen feature pin")
    return manifest


def publish(bucket_name, manifest):
    bucket = storage.Client().bucket(bucket_name)
    for name, digest in manifest.items():
        blob = bucket.blob("artifacts/" + name)
        if blob.exists():
            if sha256(blob.download_as_bytes()).hexdigest() != digest:
                raise ValueError(f"Existing cloud artifact differs: {name}")
            continue
        try:
            blob.upload_from_filename(str(ROOT / name), if_generation_match=0)
        except PreconditionFailed:
            if sha256(blob.download_as_bytes()).hexdigest() != digest:
                raise ValueError(f"Concurrent cloud artifact differs: {name}") from None
    blob = bucket.blob("artifacts/manifest.json")
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    if blob.exists():
        if blob.download_as_bytes() != payload:
            raise ValueError("Existing cloud manifest differs")
    else:
        blob.upload_from_string(payload, content_type="application/json", if_generation_match=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest = inventory()
    if args.apply:
        publish(args.bucket, manifest)
    print(json.dumps({"artifact_count": len(manifest), "manifest_sha256": sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "uploaded": args.apply}))


if __name__ == "__main__":
    main()
