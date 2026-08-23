"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-08-23 | Revision: 1367
"""

import math

def compute_step_1367(val: float) -> dict:
    factor = 8
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 1367, "val": processed}

if __name__ == '__main__':
    out = compute_step_1367(1.0)
    print(out)
