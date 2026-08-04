"""Wave-CoAtNet Component: class balanced loss weighting based on effective sample size
Module: loss | Date: 2026-08-04 | Revision: 987
"""

import math

def compute_step_987(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 987, "val": processed}

if __name__ == '__main__':
    out = compute_step_987(1.0)
    print(out)
