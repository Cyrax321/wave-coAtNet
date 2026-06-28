"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-06-28 | Revision: 303
"""

import math

def compute_step_303(val: float) -> dict:
    factor = 15
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 303, "val": processed}

if __name__ == '__main__':
    out = compute_step_303(1.0)
    print(out)
