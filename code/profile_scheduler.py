"""只读诊断：分别计时官方核内调度三步。"""

from __future__ import annotations

import sys
import time

from contest_io import _read_json
from evaluation_validation import read_evaluation_config
from schedule_step1 import step1_schedule
from schedule_step2 import _build_extended_graph, step2_spill_insertion
from schedule_step3 import prepare_step3_execution


graph = _read_json(sys.argv[1])
settings = read_evaluation_config(sys.argv[2])
started = time.time()
seq = step1_schedule(graph)
print(f"step1 {time.time()-started:.3f}s ops={len(seq)}", flush=True)
started = time.time()
result2 = step2_spill_insertion(graph, seq, settings["capacity"])
print(f"step2 {time.time()-started:.3f}s spills={len(result2['spill_records'])}", flush=True)
started = time.time()
ext = _build_extended_graph(graph, result2)
prepared = prepare_step3_execution(ext, settings["capacity"], settings["bandwidth"])
print(f"step3 {time.time()-started:.3f}s makespan={prepared['step3']['makespan']}", flush=True)
