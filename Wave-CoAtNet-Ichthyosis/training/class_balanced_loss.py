"""Wave-CoAtNet Component: class balanced loss weighting based on effective sample size
Module: loss | Date: 2026-08-27 | Revision: 1407
"""

import math

def compute_step_1407(val: float) -> dict:
    factor = 14
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 1407, "val": processed}

if __name__ == '__main__':
    out = compute_step_1407(1.0)
    print(out)
