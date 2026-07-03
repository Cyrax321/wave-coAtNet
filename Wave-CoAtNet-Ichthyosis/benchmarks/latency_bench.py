"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-07-03 | Revision: 387
"""

import math

def compute_step_387(val: float) -> dict:
    factor = 14
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 387, "val": processed}

if __name__ == '__main__':
    out = compute_step_387(1.0)
    print(out)
