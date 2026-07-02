"""Wave-CoAtNet Component: class balanced loss weighting based on effective sample size
Module: loss | Date: 2026-07-02 | Revision: 371
"""

import math

def compute_step_371(val: float) -> dict:
    factor = 15
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 371, "val": processed}

if __name__ == '__main__':
    out = compute_step_371(1.0)
    print(out)
