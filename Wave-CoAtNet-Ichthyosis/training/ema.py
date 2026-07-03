"""Wave-CoAtNet Component: exponential moving average weight tracking across epochs
Module: optim | Date: 2026-07-03 | Revision: 375
"""

import math

def compute_step_375(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "optim", "step": 375, "val": processed}

if __name__ == '__main__':
    out = compute_step_375(1.0)
    print(out)
