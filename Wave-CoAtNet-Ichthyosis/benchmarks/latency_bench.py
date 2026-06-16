"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-06-16 | Revision: 23
"""

import math

def compute_step_23(val: float) -> dict:
    factor = 7
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 23, "val": processed}

if __name__ == '__main__':
    out = compute_step_23(1.0)
    print(out)
