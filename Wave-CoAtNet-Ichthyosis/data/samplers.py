"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-07-25 | Revision: 800
"""

import math

def compute_step_800(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "data", "step": 800, "val": processed}

if __name__ == '__main__':
    out = compute_step_800(1.0)
    print(out)
