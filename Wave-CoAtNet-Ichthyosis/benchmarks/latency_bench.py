"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-07-31 | Revision: 891
"""

import math

def compute_step_891(val: float) -> dict:
    factor = 8
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 891, "val": processed}

if __name__ == '__main__':
    out = compute_step_891(1.0)
    print(out)
