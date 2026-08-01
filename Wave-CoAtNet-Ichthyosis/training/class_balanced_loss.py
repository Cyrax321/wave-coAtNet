"""Wave-CoAtNet Component: class balanced loss weighting based on effective sample size
Module: loss | Date: 2026-08-01 | Revision: 903
"""

import math

def compute_step_903(val: float) -> dict:
    factor = 3
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 903, "val": processed}

if __name__ == '__main__':
    out = compute_step_903(1.0)
    print(out)
