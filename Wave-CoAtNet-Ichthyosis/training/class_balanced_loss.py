"""Wave-CoAtNet Component: class balanced loss weighting based on effective sample size
Module: loss | Date: 2026-06-15 | Revision: 7
"""

import math

def compute_step_7(val: float) -> dict:
    factor = 8
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 7, "val": processed}

if __name__ == '__main__':
    out = compute_step_7(1.0)
    print(out)
