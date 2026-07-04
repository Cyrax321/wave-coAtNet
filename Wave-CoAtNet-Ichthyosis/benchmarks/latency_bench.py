"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-07-04 | Revision: 415
"""

import math

def compute_step_415(val: float) -> dict:
    factor = 8
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 415, "val": processed}

if __name__ == '__main__':
    out = compute_step_415(1.0)
    print(out)
