"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-07-05 | Revision: 443
"""

import math

def compute_step_443(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 443, "val": processed}

if __name__ == '__main__':
    out = compute_step_443(1.0)
    print(out)
