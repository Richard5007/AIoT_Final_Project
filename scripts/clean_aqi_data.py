#!/usr/bin/env python3
"""Validate and normalize MOENV AQX_P_488 monthly CSV archives.

The source files remain untouched. Records are keyed by (siteid, datacreationdate).
Localized Chinese/English copies are collapsed. If the same key has conflicting
numeric observations, every variant is sent to a conflict file and excluded from
the analysis-ready output rather than choosing an arbitrary value.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

EXPECTED_COLUMNS = {
    "sitename", "county", "aqi", "pollutant", "status", "so2", "so2_avg",
    "co", "co_8hr", "o3", "o3_8hr", "pm10", "pm10_avg", "pm2.5",
    "pm2.5_avg", "no2", "nox", "no", "windspeed", "winddirec",
    "datacreationdate", "longitude", "latitude", "siteid", "unit",
}
NUMERIC_COLUMNS = {
    "aqi", "so2", "so2_avg", "co", "co_8hr", "o3", "o3_8hr", "pm10",
    "pm10_avg", "pm2.5", "pm2.5_avg", "no2", "nox", "no", "windspeed",
    "winddirec", "longitude", "latitude",
}
MISSING = {"", "-", "--", "na", "n/a", "null", "none"}


def number(value: str | None) -> float | None:
    if value is None or value.strip().lower() in MISSING:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def has_cjk(value: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" for char in value)


def canonical_row(rows: list[dict[str, str]]) -> dict[str, str]:
    """Prefer Chinese display labels and fill missing fields from other copies."""
    rows = sorted(rows, key=lambda row: not (has_cjk(row.get("sitename", "")) or has_cjk(row.get("county", ""))))
    result = dict(rows[0])
    for column in result:
        if result[column].strip().lower() in MISSING:
            result[column] = next(
                (row[column] for row in rows if row[column].strip().lower() not in MISSING),
                "",
            )
    return result


def month_sort_key(path: Path) -> tuple[int, int, str]:
    match = re.search(r"\((\d{4})-(\d{2})\)\.csv$", path.name)
    if match:
        return int(match.group(1)), int(match.group(2)), path.name
    # The untagged archive is the latest/current month.
    return 9999, 99, path.name


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def station_location_key(row: dict[str, str]) -> tuple[str, float | None, float | None]:
    return (row["county"].strip(), number(row["longitude"]), number(row["latitude"]))


def build_location_index(sources: list[Path]) -> dict[tuple[str, float | None, float | None], set[str]]:
    """Index unambiguous station IDs by county and exact coordinates."""
    index: dict[tuple[str, float | None, float | None], set[str]] = defaultdict(set)
    for source in sources:
        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                site_id = row["siteid"].strip()
                key = station_location_key(row)
                if site_id and key[0] and key[1] is not None and key[2] is not None:
                    index[key].add(site_id)
    return index


def process_file(
    source: Path,
    clean_writer: csv.DictWriter,
    conflict_writer: csv.DictWriter,
    location_index: dict[tuple[str, float | None, float | None], set[str]],
) -> dict:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    unkeyed_rows = []
    recovered_siteid_rows = 0
    source_row_count = 0
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        missing = EXPECTED_COLUMNS - set(headers)
        if missing:
            raise ValueError(f"{source.name}: missing expected columns: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            source_row_count += 1
            timestamp = row["datacreationdate"].strip()
            try:
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M")
            except ValueError as error:
                raise ValueError(f"{source.name}:{line_number}: invalid timestamp {timestamp!r}") from error
            if not row["siteid"].strip():
                candidates = location_index.get(station_location_key(row), set())
                if len(candidates) == 1:
                    row["siteid"] = next(iter(candidates))
                    recovered_siteid_rows += 1
                else:
                    unkeyed_rows.append(row)
                    continue
            groups[(row["siteid"].strip(), timestamp)].append(row)

    stats = Counter()
    conflict_field_keys = Counter()
    stats["source_rows"] = source_row_count
    stats["recovered_siteid_rows"] = recovered_siteid_rows
    timestamps = []
    station_ids = set()
    for row in unkeyed_rows:
        conflict_writer.writerow({
            **row,
            "source_file": source.name,
            "conflict_reason": json.dumps({"siteid": "missing"}, ensure_ascii=False),
        })
    stats["missing_siteid_rows_excluded"] = len(unkeyed_rows)
    for (site_id, timestamp), rows in groups.items():
        station_ids.add(site_id)
        timestamps.append(timestamp)
        if len(rows) > 1:
            stats["duplicate_keys_collapsed"] += 1
            stats["duplicate_rows_removed"] += len(rows) - 1

        conflicts = {}
        for column in NUMERIC_COLUMNS:
            values = {parsed for row in rows if (parsed := number(row[column])) is not None}
            if len(values) > 1:
                conflicts[column] = sorted(values)

        if conflicts:
            stats["conflict_keys_excluded"] += 1
            stats["conflict_rows_excluded"] += len(rows)
            conflict_field_keys.update(conflicts.keys())
            reason = json.dumps(conflicts, ensure_ascii=False, sort_keys=True)
            for row in rows:
                conflict_writer.writerow({**row, "source_file": source.name, "conflict_reason": reason})
            continue

        clean_writer.writerow(canonical_row(rows))
        stats["clean_rows"] += 1

    stats["station_count"] = len(station_ids)
    for field, count in conflict_field_keys.items():
        stats[f"conflict_field_{field}"] = count
    stats["first_timestamp"] = min(timestamps) if timestamps else ""
    stats["last_timestamp"] = max(timestamps) if timestamps else ""
    stats["md5"] = md5(source)
    stats["source_file"] = source.name
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/AQX_P_488_Resource"))
    parser.add_argument("--output", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    sources = sorted(args.input.glob("*.csv"), key=month_sort_key)
    if not sources:
        raise SystemExit(f"No CSV files found in {args.input}")

    args.output.mkdir(parents=True, exist_ok=True)
    clean_path = args.output / "aqi_2026_clean.csv"
    conflicts_path = args.output / "aqi_2026_conflicts.csv"
    report_path = args.output / "cleaning_report.md"
    report_rows = []
    totals = Counter()
    with sources[0].open("r", encoding="utf-8-sig", newline="") as stream:
        columns = csv.DictReader(stream).fieldnames
    if columns is None:
        raise ValueError(f"{sources[0].name}: empty CSV")
    location_index = build_location_index(sources)

    with clean_path.open("w", encoding="utf-8-sig", newline="") as clean_stream, conflicts_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as conflict_stream:
        clean_writer = csv.DictWriter(clean_stream, fieldnames=columns, extrasaction="ignore")
        clean_writer.writeheader()
        conflict_writer = csv.DictWriter(
            conflict_stream,
            fieldnames=[*columns, "source_file", "conflict_reason"],
            extrasaction="ignore",
        )
        conflict_writer.writeheader()
        for source in sources:
            with source.open("r", encoding="utf-8-sig", newline="") as stream:
                if csv.DictReader(stream).fieldnames != columns:
                    raise ValueError(f"{source.name}: column schema differs from {sources[0].name}")
            stats = process_file(source, clean_writer, conflict_writer, location_index)
            report_rows.append(stats)
            totals.update({key: value for key, value in stats.items() if isinstance(value, int)})

    first = min(row["first_timestamp"] for row in report_rows if row["first_timestamp"])
    last = max(row["last_timestamp"] for row in report_rows if row["last_timestamp"])
    lines = [
        "# AQX_P_488 清理報告",
        "",
        f"執行時間：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"來源檔案：{len(sources)} 個；時間範圍：{first} 至 {last}",
        f"原始列數：{totals['source_rows']:,}；整理後列數：{totals['clean_rows']:,}",
        f"合併的重複測站時間鍵：{totals['duplicate_keys_collapsed']:,}",
        f"合併時移除的重複列：{totals['duplicate_rows_removed']:,}",
        f"衝突數值鍵：{totals['conflict_keys_excluded']:,}（隔離原始列 {totals['conflict_rows_excluded']:,}）；"
        f"依唯一縣市與座標補回測站編號：{totals['recovered_siteid_rows']:,}；"
        f"仍無法識別測站編號而隔離：{totals['missing_siteid_rows_excluded']:,} 列",
        f"衝突欄位鍵數：AQI {totals['conflict_field_aqi']:,}、"
        f"PM2.5_AVG {totals['conflict_field_pm2.5_avg']:,}、"
        f"PM10_AVG {totals['conflict_field_pm10_avg']:,}（欄位間可能重疊）",
        "",
        "## 方法",
        "",
        "- 以 `siteid + datacreationdate` 作為觀測鍵；不使用可能中英不同的測站名稱作為鍵。",
        "- 重複列數值一致時合併為一列；顯示名稱優先保留中文，其他欄位以非缺值補齊。",
        "- 同一觀測鍵若任一數值欄位有不同的非缺值，整組列入衝突檔，不放入分析資料。",
        "- `-`、`--`、`NA` 等缺值標記轉為空欄；原始來源檔保持不變。",
        "- 原始 CSV 不修改；本腳本可重跑，並逐檔記錄 MD5。",
        "",
        "## 各檔案檢查結果",
        "",
        "| 檔案 | 原始列數 | 測站數 | 清理後列數 | 合併重複鍵 | 重複列數 | 衝突鍵 | 補回測站編號 | 隔離無編號列 | 起始時間 | 結束時間 | MD5 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for row in report_rows:
        lines.append(
            f"| `{row['source_file']}` | {row['source_rows']:,} | {row['station_count']} | "
            f"{row['clean_rows']:,} | {row['duplicate_keys_collapsed']:,} | "
            f"{row['duplicate_rows_removed']:,} | {row['conflict_keys_excluded']:,} | "
            f"{row['recovered_siteid_rows']:,} | {row['missing_siteid_rows_excluded']:,} | "
            f"{row['first_timestamp']} | "
            f"{row['last_timestamp']} | `{row['md5']}` |"
        )
    lines += [
        "",
        "## 輸出",
        "",
        f"- 分析資料：`{clean_path.as_posix()}`",
        f"- 排除衝突的原始列與差異欄位：`{conflicts_path.as_posix()}`",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:8]))
    print(f"\nWrote {clean_path}, {conflicts_path}, and {report_path}")


if __name__ == "__main__":
    main()
