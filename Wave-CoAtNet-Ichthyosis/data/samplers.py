"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-06-28 | Revision: 324
"""

import math

def compute_step_324(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "data", "step": 324, "val": processed}

if __name__ == '__main__':
    out = compute_step_324(1.0)
    print(out)
