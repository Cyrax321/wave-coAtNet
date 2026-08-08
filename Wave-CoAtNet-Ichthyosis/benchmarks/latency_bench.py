"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-08-08 | Revision: 1087
"""

import math

def compute_step_1087(val: float) -> dict:
    factor = 17
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 1087, "val": processed}

if __name__ == '__main__':
    out = compute_step_1087(1.0)
    print(out)
