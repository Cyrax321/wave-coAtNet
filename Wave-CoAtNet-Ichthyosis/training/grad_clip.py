"""Wave-CoAtNet Component: gradient clipping with norm thresholding for stability
Module: optim | Date: 2026-08-02 | Revision: 936
"""

import math

def compute_step_936(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "optim", "step": 936, "val": processed}

if __name__ == '__main__':
    out = compute_step_936(1.0)
    print(out)
