"""补跑并回写四批结果中的 1 核只读 L2 评估。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from contest_io import _read_json
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config
from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config
from solution_multicore import build_plan


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main():
    config = str(DATA / "config.txt")
    settings = read_evaluation_config(config)
    scene = read_scene_b_config(config)
    cache = read_cache_config(config)
    for batch in range(1, 5):
        directory = ROOT / "analysis_results" / f"batch{batch}"
        path = directory / "all_results.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        fields = list(rows[0])
        for row in rows:
            if int(row["cores"]) != 1:
                continue
            graph = _read_json(str(DATA / f"{row['case']}.json"))
            plan = build_plan(graph, 1, problem=2)
            result = evaluate_problem_3(
                graph, plan, settings["bandwidth"], settings["capacity"],
                scene["cross_core_copy_delay_cycles"],
                cache["cache_capacity_bytes"],
                cache["cache_bandwidth_bytes_per_cycle"],
            )
            stats = result["cache_stats"]
            row["p3_makespan"] = str(result["makespan"])
            row["p3_vs_no_l2_speedup"] = str(int(row["p2_makespan"]) / result["makespan"])
            row["p3_added_copy_bytes"] = str(result["data_movement_bytes"]["added_copy_bytes"])
            row["p3_cache_hit_rate"] = str(stats["hit_rate"])
            row["p3_cache_hits"] = str(stats["hits"])
            row["p3_cache_accesses"] = str(stats["accesses"])
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        (directory / "all_results.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"batch{batch} updated", flush=True)


if __name__ == "__main__":
    main()
