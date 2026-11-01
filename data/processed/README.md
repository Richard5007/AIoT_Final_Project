# Processed data

Run `python scripts/clean_aqi_data.py` from the project root after placing source CSVs in `data/raw/AQX_P_488_Resource/`.

- `aqi_2026_clean.csv` is the analysis-ready output.
- `aqi_2026_conflicts.csv` contains every source variant excluded because numeric values conflict or no station ID could be recovered safely.
- `cleaning_report.md` records coverage, handling rules, counts, and checksums.

The CSV outputs are reproducible local artifacts and are excluded from Git. Do not edit the raw source files; edit the cleanup script if the policy needs to change, then regenerate and review the report.
