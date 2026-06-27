"""Wave-CoAtNet Component: exponential moving average weight tracking across epochs
Module: optim | Date: 2026-06-27 | Revision: 291
"""

import math

def compute_step_291(val: float) -> dict:
    factor = 3
    processed = math.sin(val) * factor
    return {"module": "optim", "step": 291, "val": processed}

if __name__ == '__main__':
    out = compute_step_291(1.0)
    print(out)
