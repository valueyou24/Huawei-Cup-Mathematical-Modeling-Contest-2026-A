"""在全部正式用例上运行 1--5 核实验并输出紧凑 CSV/JSON 汇总。"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from contest_io import _read_json
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_1 import evaluate_scene_a, read_scene_a_config
from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config
from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config
from singlecore_evaluate import evaluate_singlecore
from solution_multicore import build_plan


FIELDS = [
    "case", "ops", "tensors", "edges", "cores", "singlecore_makespan",
    "p1_makespan", "p1_speedup", "p1_added_copy_bytes",
    "p2_makespan", "p2_speedup", "p2_added_copy_bytes",
    "p3_makespan", "p3_vs_no_l2_speedup", "p3_added_copy_bytes",
    "p3_cache_hit_rate", "p3_cache_hits", "p3_cache_accesses",
]


def compact_row(case, graph, cores, baseline, p1, p2, p3):
    p1_move = p1["data_movement_bytes"]
    p2_move = p2["data_movement_bytes"]
    p3_move = p3["data_movement_bytes"]
    cache = p3.get("cache_stats", {})
    return {
        "case": case,
        "ops": len(graph["ops"]),
        "tensors": len(graph["tensors"]),
        "edges": len(graph["edges"]),
        "cores": cores,
        "singlecore_makespan": baseline,
        "p1_makespan": p1["makespan"],
        "p1_speedup": baseline / p1["makespan"] if p1["makespan"] else 0,
        "p1_added_copy_bytes": p1_move["added_copy_bytes"],
        "p2_makespan": p2["makespan"],
        "p2_speedup": baseline / p2["makespan"] if p2["makespan"] else 0,
        "p2_added_copy_bytes": p2_move["added_copy_bytes"],
        "p3_makespan": p3["makespan"],
        "p3_vs_no_l2_speedup": p2["makespan"] / p3["makespan"] if p3["makespan"] else 0,
        "p3_added_copy_bytes": p3_move["added_copy_bytes"],
        "p3_cache_hit_rate": cache.get("hit_rate", 0),
        "p3_cache_hits": cache.get("hits", 0),
        "p3_cache_accesses": cache.get("accesses", 0),
    }


def write_outputs(rows, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "all_results.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "all_results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="analysis_results/full")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start", type=int, default=1)
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    config_path = str(data_dir / "config.txt")
    settings = read_evaluation_config(config_path)
    scene_a = read_scene_a_config(config_path)
    scene_b = read_scene_b_config(config_path)
    cache = read_cache_config(config_path)
    cases = sorted(data_dir.glob("case_*.json"))
    cases = cases[args.start - 1:]
    if args.limit is not None:
        cases = cases[:args.limit]

    rows = []
    failures = []
    started = time.time()
    for case_index, path in enumerate(cases, 1):
        graph = _read_json(str(path))
        case = path.stem
        try:
            stage_started = time.time()
            print(f"[{case_index}/{len(cases)}] {case} singlecore start", flush=True)
            single = evaluate_singlecore(
                graph, settings["bandwidth"], settings["capacity"],
                scene_a["task_cross_core_wait_cycles"],
                scene_a["task_same_core_wait_cycles"],
            )
            baseline = single["makespan"]
            print(f"[{case_index}/{len(cases)}] {case} singlecore done {time.time()-stage_started:.1f}s", flush=True)
            for cores in range(1, 6):
                if cores == 1:
                    p1 = p2 = single
                    plan2 = build_plan(graph, 1, problem=2)
                    p3 = evaluate_problem_3(
                        graph, plan2, settings["bandwidth"], settings["capacity"],
                        scene_b["cross_core_copy_delay_cycles"],
                        cache["cache_capacity_bytes"],
                        cache["cache_bandwidth_bytes_per_cycle"],
                    )
                else:
                    stage_started = time.time()
                    print(f"[{case_index}/{len(cases)}] {case} n={cores} plans start", flush=True)
                    plan1 = build_plan(graph, cores, problem=1)
                    plan2 = build_plan(graph, cores, problem=2)
                    print(f"[{case_index}/{len(cases)}] {case} n={cores} plans done {time.time()-stage_started:.1f}s", flush=True)
                    stage_started = time.time()
                    p1 = evaluate_scene_a(
                        graph, plan1, settings["bandwidth"], settings["capacity"],
                        scene_a["task_cross_core_wait_cycles"],
                        scene_a["task_same_core_wait_cycles"],
                    )
                    print(f"[{case_index}/{len(cases)}] {case} n={cores} p1 done {time.time()-stage_started:.1f}s", flush=True)
                    stage_started = time.time()
                    p2 = evaluate_scene_b(
                        graph, plan2, settings["bandwidth"], settings["capacity"],
                        scene_b["cross_core_copy_delay_cycles"],
                    )
                    print(f"[{case_index}/{len(cases)}] {case} n={cores} p2 done {time.time()-stage_started:.1f}s", flush=True)
                    stage_started = time.time()
                    p3 = evaluate_problem_3(
                        graph, plan2, settings["bandwidth"], settings["capacity"],
                        scene_b["cross_core_copy_delay_cycles"],
                        cache["cache_capacity_bytes"],
                        cache["cache_bandwidth_bytes_per_cycle"],
                    )
                    print(f"[{case_index}/{len(cases)}] {case} n={cores} p3 done {time.time()-stage_started:.1f}s", flush=True)
                rows.append(compact_row(case, graph, cores, baseline, p1, p2, p3))
            write_outputs(rows, output_dir)
            elapsed = time.time() - started
            print(f"[{case_index}/{len(cases)}] {case} complete; elapsed={elapsed:.1f}s", flush=True)
        except Exception as exc:  # 保留已完成案例，便于定位官方评测拒绝原因。
            failures.append({"case": case, "type": type(exc).__name__, "error": str(exc)})
            (output_dir / "failures.json").write_text(
                json.dumps(failures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[{case_index}/{len(cases)}] {case} FAILED: {type(exc).__name__}: {exc}", flush=True)
    write_outputs(rows, output_dir)
    (output_dir / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"done: rows={len(rows)} failures={len(failures)} elapsed={time.time()-started:.1f}s")


if __name__ == "__main__":
    raise SystemExit(main())
