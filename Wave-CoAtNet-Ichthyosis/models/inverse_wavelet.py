"""Wave-CoAtNet Component: inverse wavelet reconstruction block with steerable filters
Module: arch | Date: 2026-07-04 | Revision: 421
"""

import math

def compute_step_421(val: float) -> dict:
    factor = 14
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 421, "val": processed}

if __name__ == '__main__':
    out = compute_step_421(1.0)
    print(out)
