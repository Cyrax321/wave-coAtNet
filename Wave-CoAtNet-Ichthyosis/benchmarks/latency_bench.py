"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-07-21 | Revision: 723
"""

import math

def compute_step_723(val: float) -> dict:
    factor = 10
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 723, "val": processed}

if __name__ == '__main__':
    out = compute_step_723(1.0)
    print(out)
