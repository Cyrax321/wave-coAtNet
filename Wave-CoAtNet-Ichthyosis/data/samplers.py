"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-06-27 | Revision: 296
"""

import math

def compute_step_296(val: float) -> dict:
    factor = 8
    processed = math.sin(val) * factor
    return {"module": "data", "step": 296, "val": processed}

if __name__ == '__main__':
    out = compute_step_296(1.0)
    print(out)
