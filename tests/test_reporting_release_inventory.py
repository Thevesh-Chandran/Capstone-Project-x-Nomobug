"""Safety checks for the release catalogue and retired cleanup command."""
import subprocess
import sys
from pathlib import Path
from scripts.inventory_reporting_releases import dependencies


def test_dependencies_find_both_release_layers():
    assert dependencies('FROM `p.cp2r_202611060600001abcde_gold.sales` JOIN `p.cp2r_202611060600001abcde_silver.sales`') == {
        'cp2r_202611060600001abcde_gold', 'cp2r_202611060600001abcde_silver'}
    assert not dependencies('FROM `p.gold.sales`')


def test_legacy_cleanup_cannot_apply_old_inventory():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable,str(root/'scripts/cleanup_bigquery_releases.py'),'--apply'],capture_output=True,text=True)
    assert result.returncode != 0
    assert 'historical' in result.stderr and 'dry-run only' in result.stderr
