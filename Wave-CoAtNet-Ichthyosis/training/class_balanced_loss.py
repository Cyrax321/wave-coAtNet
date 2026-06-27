"""Wave-CoAtNet Component: class balanced loss weighting based on effective sample size
Module: loss | Date: 2026-06-27 | Revision: 287
"""

import math

def compute_step_287(val: float) -> dict:
    factor = 16
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 287, "val": processed}

if __name__ == '__main__':
    out = compute_step_287(1.0)
    print(out)
