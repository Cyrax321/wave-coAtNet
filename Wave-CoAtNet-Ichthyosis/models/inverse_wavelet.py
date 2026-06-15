"""Wave-CoAtNet Component: inverse wavelet reconstruction block with steerable filters
Module: arch | Date: 2026-06-15 | Revision: 1
"""

import math

def compute_step_1(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 1, "val": processed}

if __name__ == '__main__':
    out = compute_step_1(1.0)
    print(out)
