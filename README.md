# Taiwan Air Quality Evidence Agent

台灣空氣品質證據分析代理人：以公開逐時監測資料，回答特定地點與時段的空品趨勢、事件與測站差異，並附上觀測值、時間、來源和限制。

## Project status

Proposal-stage materials are prepared. The proposal includes the required sections, literature synthesis, Deep Research, Agent architecture, flowchart, pseudocode, and evaluation plan. The downloaded AQX_P_488 data has a reproducible first-pass cleanup. Agent experiments and implementation have not yet been completed.

## Project files

- `Proposal.md` — Full proposal source with Abstract, Introduction, Related Work, Deep Research, Proposed Scheme, evaluation, and references.
- `DESIGN.md` — Living system design, architecture, data flow, assumptions, evaluation, and limitations.
- `output/Proposal.docx` — Formatted Proposal Document.
- `output/Proposal.pptx` — 17-slide Proposal PPT, including Agent design, architecture, flowchart, pseudocode, and evaluation.
- `research/data-source-inventory.md` — Data-source inventory, audited sample, schema, and coverage limitations.
- `scripts/clean_aqi_data.py` — Reproducible validation and cleanup for the downloaded AQX_P_488 monthly archives.
- `data/processed/cleaning_report.md` — Audited row counts, duplicate/conflict handling, date coverage, and source-file checksums.

## Primary data source

The proposal MVP uses the Taiwan Ministry of Environment historical hourly AQI dataset, AQX_P_488: <https://data.moenv.gov.tw/dataset/detail/aqx_p_488>. The current local sample covers 2026-01-01 through 2026-10-29 16:00. AQX_P_432 and low-cost IoT sensor data are optional extensions, not required for the proposed evaluation.

The Ministry's air-pollution IoT observations are a possible finer-resolution extension: <https://env.moenv.gov.tw/en/Issue/Index/53b6ae55-bb69-449e-953e-01c2330ca3b8>. Sensor integration depends on verifying API access, historical retention, station correspondence, and quality metadata.

## Data and evidence principles

- Preserve source records and retrieval time; document timezone and units.
- Treat missing, stale, duplicate, or conflicting values as quality flags.
- Keep station observations distinct from personal exposure.
- Do not claim pollutant causes or individualized health outcomes without appropriate evidence.
- Never commit API credentials. Store them in a local environment variable or an ignored configuration file.

## How to run

### Local data preparation

Place the original monthly AQX_P_488 CSV exports in `data/raw/AQX_P_488_Resource/`, then run:

```powershell
python scripts/clean_aqi_data.py
```

The script writes `data/processed/aqi_2026_clean.csv`, an audit file `data/processed/aqi_2026_conflicts.csv`, and the tracked summary `data/processed/cleaning_report.md`. It collapses bilingual copies by station ID and timestamp, restores a missing station ID only when county and coordinates identify exactly one known station, and isolates any key with conflicting numeric values. Raw and generated CSVs are intentionally excluded from Git because they are large; the script, report, and checksums document the reproducible process.

## License and attribution

The project will follow the source dataset's current open-data license and include attribution for all datasets and research sources. Confirm exact license terms before distributing any data extracts.
