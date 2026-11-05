"""Refresh navigation and inventory without executing notebooks or changing evidence.

Use --clean-caches to remove only regenerable caches outside protected folders.
"""
import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import stat

ROOT = Path(__file__).resolve().parents[1]
CACHES = {'__pycache__', '.pytest_cache', '.ruff_cache', '.ipynb_checkpoints'}
PROTECTED = {'.git', '.venv', 'secrets', 'data', 'outputs', 'archive', 'tmp', '.codex-tmp', '.codex-qa'}
AREAS = {'notebooks':'Analysis notebooks','scripts':'Processing and model code','dbt':'Warehouse SQL',
         'webapp':'Website','config':'Rules and protocols','tests':'Tests','infra':'Hosting',
         'planning':'Specifications and dated records','docs':'Report documents',
         'outputs':'Results and evidence','data':'Private data','archive':'Retired material',
         'project_guide':'File guides','templates':'Templates','.github':'Automation'}


def walk(base, skip=()):
    for parent, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = [d for d in dirs if d not in skip and not (Path(parent)/d).is_symlink()]
        for name in files:
            p=Path(parent)/name
            if not p.is_symlink(): yield p


def describe(p):
    fallback=p.stem.replace('_',' ').replace('-',' ')
    if p.suffix not in {'.py','.md'}: return fallback
    try:
        text=p.read_text(encoding='utf-8-sig')
        if p.suffix=='.py': return (ast.get_docstring(ast.parse(text)) or fallback).splitlines()[0]
        if p.suffix=='.md': return next((s[2:] for s in text.splitlines() if s.startswith('# ')),fallback)
    except (OSError,UnicodeError,SyntaxError): pass
    return fallback


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clean-caches',action='store_true');args=parser.parse_args()
    removed=[]
    if args.clean_caches:
        for parent,dirs,_ in os.walk(ROOT,followlinks=False):
            for name in list(dirs):
                p=Path(parent)/name
                if name in PROTECTED or p.is_symlink() or ('dbt' in p.parts and name in {'target','logs','dbt_packages'}):
                    dirs.remove(name)
                elif name in CACHES:
                    dirs.remove(name);resolved=p.resolve()
                    if not resolved.is_relative_to(ROOT.resolve()) or resolved.name not in CACHES:
                        raise ValueError('Invalid cleanup target')
                    removed.append({'path':p.relative_to(ROOT).as_posix(),'bytes':sum(f.stat().st_size for f in walk(p))})
                    def clear_readonly(function, filename, error):
                        Path(filename).chmod(stat.S_IWRITE | stat.S_IREAD)
                        function(filename)
                    shutil.rmtree(resolved,onexc=clear_readonly)
    sizes=[]
    for p in sorted(ROOT.iterdir()):
        if p.name in {'.git','secrets','.env'}: continue
        fs=list(walk(p)) if p.is_dir() else [p]
        sizes.append({'Folder':p.name,'Files':len(fs),'Bytes':sum(f.stat().st_size for f in fs)})
    rows=[];hashes={}
    for folder,label in AREAS.items():
        if folder in {'outputs','data','docs','archive'}: continue
        for p in sorted(walk(ROOT/folder,CACHES|{'target','logs','dbt_packages'})):
            if 'evidence' in p.parts or p.suffix.lower() not in {'.py','.sql','.md','.yaml','.yml','.json','.ps1','.js','.css','.html','.ipynb','.txt'}: continue
            rows.append({'Area':label,'File':p.relative_to(ROOT).as_posix(),'Purpose':describe(p)})
            if folder=='scripts' and p.suffix=='.py' and p.stat().st_size:
                hashes.setdefault(hashlib.sha256(p.read_bytes()).hexdigest(),[]).append(p.relative_to(ROOT).as_posix())
    guide=ROOT/'project_guide'
    for name,records in [('File_Catalogue.csv',rows),('Folder_Sizes.csv',sizes)]:
        with (guide/name).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    e=html.escape
    cards=''.join(f'<a class="card" href="{e(folder)}/"><b>{e(label)}</b><code>{e(folder)}/</code></a>' for folder,label in AREAS.items())
    books=''.join(f'<li><a href="{p.relative_to(ROOT).as_posix()}">{e(p.stem.replace("_"," "))}</a> · <a href="{p.with_suffix(".ipynb").relative_to(ROOT).as_posix()}">Jupyter</a></li>' for p in sorted((ROOT/'notebooks').glob('[0-9][0-9]_*.html')))
    table=''.join(f'<tr><td>{e(r["Area"])}</td><td><a href="{e(r["File"])}">{e(r["File"])}</a></td><td>{e(r["Purpose"])}</td></tr>' for r in rows)
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nomobug project files</title><style>body{margin:0;background:#f3f5f9;color:#172033;font:15px/1.6 system-ui}main{max-width:1180px;margin:auto;padding:40px 28px}h1{font-size:36px}h2{margin-top:36px}a{color:#1f4fe0}header{border-bottom:2px solid #172033;padding-bottom:22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}.card{background:white;border:1px solid #dde1ea;padding:18px;text-decoration:none;color:inherit}.card b,.card code{display:block}.card code{color:#1f4fe0}input,select{padding:12px;border:1px solid #cbd2e0;margin:8px 8px 16px 0}input{width:55%}table{width:100%;border-collapse:collapse;background:white;font-size:13px}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #e3e7ee;overflow-wrap:anywhere}th{background:#e7edf9}.note{padding:16px;background:#e7edf9}</style><main><header><p>NOMOBUG / CAPSTONE PROJECT</p><h1>Project files</h1><p>Data → cleaning → experiments → application → cloud operation</p><a href="START_HERE.md">Start here</a> · <a href="project_guide/Project_Structure.md">Folder guide</a> · <a href="project_guide/File_Catalogue.csv">File list</a> · <a href="project_guide/Folder_Sizes.csv">Folder sizes</a></header><h2>Website versions</h2><div class="note"><a href="http://127.0.0.1:8090/#decisions">Updated local preview</a> (this laptop, while running) · <a href="https://cp2-portal-964813222593.asia-southeast1.run.app/#home">Hosted portal</a><br>The current website source is deployed in revision cp2-portal-00087-cep. Metabase on Vercel is a separate blocked compatibility trial.</div><h2>Folders</h2><div class="grid">'''+cards+'''</div><h2>Analysis notebooks</h2><p>Saved historical evidence; opening a notebook does not refresh sources or establish a new model result.</p><ol>'''+books+'''</ol><p><a href="planning/CP2_PROJECT_HANDOVER_20261102.md">2 November handover</a> · <a href="planning/CP2_OPERATIONAL_MODEL_SEARCH_20261102.md">Latest model study</a> · <a href="planning/CP2_REMAINING_TASKS_20261102.md">Remaining verification</a></p><h2>Search source files</h2><p>Imports and evidence paths remain stable. Research scripts are not automatically active models. Do not run every script.</p><input id="search" aria-label="Search files" placeholder="Search a file or purpose"><select id="area" aria-label="Project area"><option value="">All areas</option>'''+''.join(f'<option>{e(a)}</option>' for a in sorted(set(r['Area'] for r in rows)))+'''</select><table><thead><tr><th>Area</th><th>File</th><th>Purpose</th></tr></thead><tbody>'''+table+'''</tbody></table><p>Private data, credentials and raw evidence are excluded from this source index. Updated 2 November 2026.</p></main><script>function filter(){let q=document.querySelector('#search').value.toLowerCase(),a=document.querySelector('#area').value;document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q)||(a&&r.cells[0].textContent!==a))}document.querySelector('#search').addEventListener('input',filter);document.querySelector('#area').addEventListener('change',filter)</script></html>'''
    page=page.replace('<h2>Website versions</h2>','<h2>Prediction models</h2><p><a href="project_guide/models/index.html">Open the visual model guide</a>: current model, candidates, inputs, results and experiment search.</p><h2>Website versions</h2>')
    (ROOT/'FILE_GUIDE.html').write_text(page,encoding='utf-8')
    report={'at_utc':datetime.now(timezone.utc).isoformat(),'removed_caches':removed,'removed_bytes':sum(r['bytes'] for r in removed),'folders':sizes,'identical_nonempty_scripts':[v for v in hashes.values() if len(v)>1],'catalogued_files':len(rows),'protected':'Source, data, models, protocols, receipts, dbt target and cloud resources unchanged.'}
    audit=ROOT/'outputs/project_audit/20261102_folder_cleanup';audit.mkdir(parents=True,exist_ok=True)
    (audit/('cleanup_'+datetime.now(timezone.utc).strftime('%H%M%S')+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'folders','removed_caches'}},indent=2))


if __name__=='__main__':main()
