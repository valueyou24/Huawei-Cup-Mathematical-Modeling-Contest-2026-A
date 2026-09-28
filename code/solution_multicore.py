"""通信感知的多核切图与调度启发式。

算法只输出赛题要求的 node_to_subgraph/core_schedules。它先在排除原始
COPY_IN/COPY_OUT 后的操作 DAG 上求关键路径优先的拓扑序，再切成连续拓扑块，
最后用考虑 Pipe 负载、前驱完成时间与跨核通信的列表调度将块分配到核心。
连续拓扑块保证收缩后的子图依赖图仍为 DAG。
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
from collections import defaultdict
from pathlib import Path

from contest_io import _read_json
from evaluation_validation import validate_graph
from stub_multicore_cut_and_schedule import (
    EXCLUDED_COPY_TYPES,
    _build_op_adjacency,
    _contract_excluded_copy_nodes,
    validate_multicore_plan,
)


PIPES = ("PIPE_MTE2", "PIPE_MTE3", "PIPE_M", "PIPE_V")


def _edge_bytes(graph_json, eligible):
    """汇总 eligible op 之间每条依赖携带的张量字节数。"""
    op_ids = {op["id"] for op in graph_json["ops"]}
    tensor_by_id = {t["id"]: t for t in graph_json["tensors"]}
    producers = defaultdict(set)
    consumers = defaultdict(set)
    for edge in graph_json["edges"]:
        src, dst = edge["source"], edge["target"]
        if src in op_ids and dst in tensor_by_id:
            producers[dst].add(src)
        elif src in tensor_by_id and dst in op_ids:
            consumers[src].add(dst)
    weights = defaultdict(int)
    for tid, srcs in producers.items():
        size = int(tensor_by_id[tid].get("size", 0))
        for src in srcs:
            for dst in consumers.get(tid, ()):
                if src in eligible and dst in eligible and src != dst:
                    weights[(src, dst)] += size
    return weights


def _priority_topological_order(nodes, preds, succs, duration):
    """以静态底层长度为优先级的确定性 Kahn 拓扑序。"""
    indegree = {node: len(preds[node]) for node in nodes}
    plain_ready = [node for node in nodes if indegree[node] == 0]
    heapq.heapify(plain_ready)
    topo = []
    while plain_ready:
        node = heapq.heappop(plain_ready)
        topo.append(node)
        for nxt in sorted(succs[node]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(plain_ready, nxt)
    if len(topo) != len(nodes):
        raise ValueError("eligible operation graph contains a cycle")

    bottom = {}
    for node in reversed(topo):
        bottom[node] = duration[node] + max(
            (bottom[nxt] for nxt in succs[node]), default=0)

    indegree = {node: len(preds[node]) for node in nodes}
    ready = [(-bottom[node], node) for node in nodes if indegree[node] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        _, node = heapq.heappop(ready)
        order.append(node)
        for nxt in sorted(succs[node]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(ready, (-bottom[nxt], nxt))
    return order


def _make_blocks(order, duration, target_blocks):
    """按累计工作量把拓扑序切成近似等重的连续块。"""
    if not order:
        return []
    target_blocks = max(1, min(target_blocks, len(order)))
    total = sum(max(1, duration[node]) for node in order)
    target = max(1, math.ceil(total / target_blocks))
    blocks, current, work = [], [], 0
    for index, node in enumerate(order):
        remaining_nodes = len(order) - index
        remaining_blocks = target_blocks - len(blocks)
        if current and work >= target and remaining_nodes >= remaining_blocks:
            blocks.append(current)
            current, work = [], 0
        current.append(node)
        work += max(1, duration[node])
    if current:
        blocks.append(current)
    return blocks


def build_plan(graph_json, num_cores, problem=2, blocks_per_core=None):
    """生成合法方案；problem=1 使用粗粒度，problem=2/3 使用细粒度。"""
    validate_graph(graph_json)
    if num_cores < 1:
        raise ValueError("num_cores must be positive")
    op_by_id = {op["id"]: op for op in graph_json["ops"]}
    eligible = sorted(
        op_id for op_id, op in op_by_id.items()
        if op.get("op") not in EXCLUDED_COPY_TYPES
    )
    if not eligible:
        return {"node_to_subgraph": {}, "core_schedules": [[] for _ in range(num_cores)]}

    _, full_succs = _build_op_adjacency(graph_json)
    preds, succs = _contract_excluded_copy_nodes(eligible, full_succs)
    duration = {op_id: max(1, int(op_by_id[op_id].get("cycles", 1))) for op_id in eligible}
    order = _priority_topological_order(eligible, preds, succs, duration)

    if num_cores == 1:
        target_blocks = 1
    elif blocks_per_core is not None:
        target_blocks = num_cores * blocks_per_core
    else:
        target_blocks = num_cores * (6 if problem == 1 else 24)
    blocks = _make_blocks(order, duration, target_blocks)
    block_of = {node: block_id for block_id, block in enumerate(blocks) for node in block}

    block_preds = {block_id: set() for block_id in range(len(blocks))}
    block_succs = {block_id: set() for block_id in range(len(blocks))}
    edge_bytes = _edge_bytes(graph_json, set(eligible))
    block_edge_bytes = defaultdict(int)
    for src in eligible:
        for dst in succs[src]:
            bsrc, bdst = block_of[src], block_of[dst]
            if bsrc != bdst:
                block_succs[bsrc].add(bdst)
                block_preds[bdst].add(bsrc)
                block_edge_bytes[(bsrc, bdst)] += edge_bytes.get((src, dst), 0)

    block_pipe_work = []
    for block in blocks:
        work = {pipe: 0 for pipe in PIPES}
        for node in block:
            pipe = op_by_id[node].get("pipe")
            if pipe in work:
                work[pipe] += duration[node]
        block_pipe_work.append(work)

    # 块 id 沿拓扑序递增，故直接按 id 列表调度即可。
    pipe_available = [{pipe: 0.0 for pipe in PIPES} for _ in range(num_cores)]
    core_available = [0.0] * num_cores
    finish = {}
    core_of = {}
    schedules = [[] for _ in range(num_cores)]
    sync_delay = 1000 if problem == 1 else 500
    same_task_gap = 100 if problem == 1 else 0

    for block_id in range(len(blocks)):
        best = None
        for core in range(num_cores):
            ready = core_available[core] + (same_task_gap if schedules[core] else 0)
            communication = 0.0
            for pred in block_preds[block_id]:
                pred_ready = finish[pred]
                if core_of[pred] != core:
                    bytes_ = block_edge_bytes.get((pred, block_id), 0)
                    pred_ready += sync_delay + bytes_ / 60.0
                    communication += bytes_
                ready = max(ready, pred_ready)
            pipe_finish = max(
                max(pipe_available[core][pipe], ready) + work
                for pipe, work in block_pipe_work[block_id].items()
            )
            # 极小的通信项只用于确定完全相同完工时间下的选择。
            score = (pipe_finish + communication * 1e-12, pipe_finish, core)
            if best is None or score < best[0]:
                best = (score, core, ready, pipe_finish)
        _, core, ready, block_finish = best
        core_of[block_id] = core
        finish[block_id] = block_finish
        schedules[core].append(block_id)
        core_available[core] = block_finish
        for pipe, work in block_pipe_work[block_id].items():
            pipe_available[core][pipe] = max(pipe_available[core][pipe], ready) + work

    plan = {
        "node_to_subgraph": {str(node): block_of[node] for node in eligible},
        "core_schedules": schedules,
    }
    validate_multicore_plan(graph_json, plan)
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成通信感知的多核切图与调度方案")
    parser.add_argument("graph")
    parser.add_argument("-n", "--num-cores", type=int, required=True)
    parser.add_argument("-p", "--problem", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("-o", "--output")
    parser.add_argument("--blocks-per-core", type=int)
    args = parser.parse_args(argv)
    graph = _read_json(args.graph)
    plan = build_plan(
        graph, args.num_cores, problem=args.problem,
        blocks_per_core=args.blocks_per_core,
    )
    output = Path(args.output) if args.output else Path(args.graph).with_name(
        f"{Path(args.graph).stem}_multicore_res.json")
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: wrote {output}")


if __name__ == "__main__":
    raise SystemExit(main())
