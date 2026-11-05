# Project notebooks

Open 00_Project_Overview.ipynb first, then chapters 01–10 in order. HTML copies provide the same saved outputs without Jupyter.

Run from the project root with `.venv/Scripts/python.exe -m scripts.build_project_notebooks` to regenerate from pinned evidence. Individual notebooks run from this folder or the project root. Dependencies: pandas, matplotlib, scikit-learn and Jupyter/nbformat. No Google credentials or raw customer data are included in this folder.

These notebooks replay recorded aggregate evidence. Full training and source-cleaning implementations remain in scripts and dbt, with exact paths in each chapter. Chapters 09 and 10 can refit their already selected models when private rows exist; it does not repeat the model search. No notebook build publishes models.
