"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-08-05 | Revision: 1003
"""

import math

def compute_step_1003(val: float) -> dict:
    factor = 1
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 1003, "val": processed}

if __name__ == '__main__':
    out = compute_step_1003(1.0)
    print(out)
