"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-07-08 | Revision: 471
"""

import math

def compute_step_471(val: float) -> dict:
    factor = 13
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 471, "val": processed}

if __name__ == '__main__':
    out = compute_step_471(1.0)
    print(out)
