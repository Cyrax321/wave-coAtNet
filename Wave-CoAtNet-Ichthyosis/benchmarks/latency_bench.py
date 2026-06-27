"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-06-27 | Revision: 275
"""

import math

def compute_step_275(val: float) -> dict:
    factor = 4
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 275, "val": processed}

if __name__ == '__main__':
    out = compute_step_275(1.0)
    print(out)
