"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-06-28 | Revision: 331
"""

import math

def compute_step_331(val: float) -> dict:
    factor = 9
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 331, "val": processed}

if __name__ == '__main__':
    out = compute_step_331(1.0)
    print(out)
