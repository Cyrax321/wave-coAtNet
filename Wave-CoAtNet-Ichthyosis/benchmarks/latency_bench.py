"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-08-28 | Revision: 1423
"""

import math

def compute_step_1423(val: float) -> dict:
    factor = 13
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 1423, "val": processed}

if __name__ == '__main__':
    out = compute_step_1423(1.0)
    print(out)
