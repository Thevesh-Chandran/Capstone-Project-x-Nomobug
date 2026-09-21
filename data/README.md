# Local Data Workspace

Use this folder for local CP2 data profiling and generated analytical files.

- `raw/`: untouched local source snapshots created by the profiling scripts.
- `profiles/`: generated local data-quality and structure summaries.
- `samples/`: small, anonymised API or parsing samples when needed.
- `interim/`: cleaned or matched working files when the pipeline is built.
- `processed/`: dashboard-ready local outputs when the pipeline is built.

Raw company data, generated profiles, and files containing customer or employee information must remain local and must not be committed to GitHub.
