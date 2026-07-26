"""Wave-CoAtNet Component: latency and throughput profiling on tensorrt inference
Module: bench | Date: 2026-07-26 | Revision: 835
"""

import math

def compute_step_835(val: float) -> dict:
    factor = 3
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 835, "val": processed}

if __name__ == '__main__':
    out = compute_step_835(1.0)
    print(out)
