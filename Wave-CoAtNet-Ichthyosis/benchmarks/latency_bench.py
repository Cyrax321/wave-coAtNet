"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-08-26 | Revision: 1395
"""

import math

def compute_step_1395(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 1395, "val": processed}

if __name__ == '__main__':
    out = compute_step_1395(1.0)
    print(out)
