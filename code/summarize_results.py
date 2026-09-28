"""合并四批实验，校验覆盖并生成统计、SVG 曲线和逐用例附录。"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis_results" / "full"


def load_rows():
    rows = []
    for index in range(1, 5):
        path = ROOT / "analysis_results" / f"batch{index}" / "all_results.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows.extend(csv.DictReader(handle))
        failures = json.loads((path.parent / "failures.json").read_text(encoding="utf-8"))
        if failures:
            raise RuntimeError(f"batch{index} has failures: {failures}")
    numeric_int = {
        "ops", "tensors", "edges", "cores", "singlecore_makespan",
        "p1_makespan", "p1_added_copy_bytes", "p2_makespan",
        "p2_added_copy_bytes", "p3_makespan", "p3_added_copy_bytes",
        "p3_cache_hits", "p3_cache_accesses",
    }
    numeric_float = {
        "p1_speedup", "p2_speedup", "p3_vs_no_l2_speedup", "p3_cache_hit_rate"
    }
    for row in rows:
        for key in numeric_int:
            row[key] = int(row[key])
        for key in numeric_float:
            row[key] = float(row[key])
    rows.sort(key=lambda row: (row["case"], row["cores"]))
    pairs = {(row["case"], row["cores"]) for row in rows}
    cases = sorted({row["case"] for row in rows})
    if len(rows) != 500 or len(pairs) != 500 or len(cases) != 100:
        raise RuntimeError(f"coverage mismatch: rows={len(rows)} pairs={len(pairs)} cases={len(cases)}")
    for case in cases:
        if {row["cores"] for row in rows if row["case"] == case} != {1, 2, 3, 4, 5}:
            raise RuntimeError(f"core coverage mismatch: {case}")
    return rows


def mean(values):
    return statistics.fmean(values)


def make_svg(path, title, x_values, series, y_label, y_min=None):
    width, height = 760, 440
    left, right, top, bottom = 90, 35, 55, 75
    plot_w, plot_h = width - left - right, height - top - bottom
    all_y = [value for _, values, _ in series for value in values]
    low = min(all_y) if y_min is None else y_min
    high = max(all_y)
    pad = max((high - low) * 0.12, 0.02)
    low, high = max(0, low - pad), high + pad
    if high <= low:
        high = low + 1

    def px(x):
        return left + (x - min(x_values)) / (max(x_values) - min(x_values)) * plot_w

    def py(y):
        return top + (high - y) / (high - low) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-size="18" font-weight="bold">{title}</text>',
    ]
    for i in range(6):
        value = low + (high - low) * i / 5
        y = py(value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#e2e8f0"/>')
        parts.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-family="Arial" font-size="12">{value:.2f}</text>')
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#334155"/>')
    parts.append(f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#334155"/>')
    for x in x_values:
        xp = px(x)
        parts.append(f'<text x="{xp:.1f}" y="{height-bottom+25}" text-anchor="middle" font-family="Arial" font-size="13">{x}</text>')
    parts.append(f'<text x="{width/2}" y="{height-20}" text-anchor="middle" font-family="Microsoft YaHei, sans-serif" font-size="13">核心数</text>')
    parts.append(f'<text x="22" y="{height/2}" text-anchor="middle" transform="rotate(-90 22 {height/2})" font-family="Microsoft YaHei, sans-serif" font-size="13">{y_label}</text>')
    legend_x, legend_y = left + 12, top + 12
    for idx, (label, values, color) in enumerate(series):
        points = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(x_values, values))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>')
        for x, y in zip(x_values, values):
            parts.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="4" fill="{color}"/>')
        ly = legend_y + idx * 24
        parts.append(f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x+26}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<text x="{legend_x+34}" y="{ly+4}" font-family="Microsoft YaHei, sans-serif" font-size="12">{label}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")


def main():
    rows = load_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (OUT / "all_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "all_results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    by_core = defaultdict(list)
    for row in rows:
        by_core[row["cores"]].append(row)
    core_summary = []
    for cores in range(1, 6):
        group = by_core[cores]
        core_summary.append({
            "cores": cores,
            "p1_mean_speedup": mean(row["p1_speedup"] for row in group),
            "p2_mean_speedup": mean(row["p2_speedup"] for row in group),
            "p1_mean_added_copy_mib": mean(row["p1_added_copy_bytes"] for row in group) / 2**20,
            "p2_mean_added_copy_mib": mean(row["p2_added_copy_bytes"] for row in group) / 2**20,
            "p2_normalized_time": mean(row["p2_makespan"] / row["singlecore_makespan"] for row in group),
            "p3_normalized_time": mean(row["p3_makespan"] / row["singlecore_makespan"] for row in group),
            "p3_mean_vs_no_l2_speedup": mean(row["p3_vs_no_l2_speedup"] for row in group),
            "p3_mean_cache_hit_rate": mean(row["p3_cache_hit_rate"] for row in group),
            "p1_cases_faster_than_single": sum(row["p1_speedup"] > 1 for row in group),
            "p2_cases_faster_than_single": sum(row["p2_speedup"] > 1 for row in group),
            "p2_cases_faster_than_p1": sum(row["p2_makespan"] < row["p1_makespan"] for row in group),
        })

    multicore_rows = [row for row in rows if row["cores"] > 1]
    l2_better = sum(row["p3_makespan"] < row["p2_makespan"] for row in multicore_rows)
    l2_equal = sum(row["p3_makespan"] == row["p2_makespan"] for row in multicore_rows)
    l2_worse = sum(row["p3_makespan"] > row["p2_makespan"] for row in multicore_rows)
    best_p1 = max(rows, key=lambda row: row["p1_speedup"])
    best_p2 = max(rows, key=lambda row: row["p2_speedup"])
    best_l2 = max(rows, key=lambda row: row["p3_vs_no_l2_speedup"])
    worst_l2 = min(multicore_rows, key=lambda row: row["p3_vs_no_l2_speedup"])
    summary = {
        "coverage": {"rows": len(rows), "cases": 100, "core_counts": [1, 2, 3, 4, 5], "failures": 0},
        "by_core": core_summary,
        "l2_outcomes_multicore": {"better": l2_better, "equal": l2_equal, "worse": l2_worse},
        "best_p1": best_p1,
        "best_p2": best_p2,
        "best_l2": best_l2,
        "worst_l2": worst_l2,
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    x = [item["cores"] for item in core_summary]
    make_svg(
        OUT / "speedup.svg", "场景 A 与场景 B 的平均加速比", x,
        [
            ("问题 1 场景 A", [item["p1_mean_speedup"] for item in core_summary], "#2563eb"),
            ("问题 2 场景 B", [item["p2_mean_speedup"] for item in core_summary], "#dc2626"),
        ], "平均加速比", y_min=0,
    )
    make_svg(
        OUT / "l2_comparison.svg", "无 L2 与只读 L2 的平均归一化执行时间", x,
        [
            ("无 L2", [item["p2_normalized_time"] for item in core_summary], "#7c3aed"),
            ("只读 L2", [item["p3_normalized_time"] for item in core_summary], "#059669"),
        ], "相对单核执行时间", y_min=0,
    )

    appendix = [
        "# 全部测试用例评估明细",
        "",
        "下表全部数值由题目提供的评估函数在固定 `config.txt` 下计算。新增搬运量单位为 MiB，Cache 命中率为按字节统计的命中率。",
        "",
        "| 用例 | 核数 | 单核 Makespan | 问题1 Makespan | 问题1加速比 | 问题1新增搬运 MiB | 问题2 Makespan | 问题2加速比 | 问题2新增搬运 MiB | 问题3 Makespan | L2相对无L2加速比 | Cache命中率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        appendix.append(
            f"| {row['case']} | {row['cores']} | {row['singlecore_makespan']} | "
            f"{row['p1_makespan']} | {row['p1_speedup']:.4f} | {row['p1_added_copy_bytes']/2**20:.3f} | "
            f"{row['p2_makespan']} | {row['p2_speedup']:.4f} | {row['p2_added_copy_bytes']/2**20:.3f} | "
            f"{row['p3_makespan']} | {row['p3_vs_no_l2_speedup']:.4f} | {row['p3_cache_hit_rate']:.2%} |"
        )
    (OUT / "全部用例评估明细.md").write_text("\n".join(appendix) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
