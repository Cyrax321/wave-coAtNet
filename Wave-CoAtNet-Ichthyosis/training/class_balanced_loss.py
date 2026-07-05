"""Wave-CoAtNet Component: class balanced loss weighting based on effective sample size
Module: loss | Date: 2026-07-05 | Revision: 427
"""

import math

def compute_step_427(val: float) -> dict:
    factor = 3
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 427, "val": processed}

if __name__ == '__main__':
    out = compute_step_427(1.0)
    print(out)
