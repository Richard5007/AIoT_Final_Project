# Raw data

Place unmodified monthly MOENV AQX_P_488 CSV exports in `AQX_P_488_Resource/`.

Source: <https://data.moenv.gov.tw/dataset/detail/aqx_p_488>

The source files are intentionally not tracked by Git because they are large. Record the retrieval date and retain the original filenames. Run `python scripts/clean_aqi_data.py` to regenerate local processed files; checksums and cleanup results are summarized in `data/processed/cleaning_report.md`.
