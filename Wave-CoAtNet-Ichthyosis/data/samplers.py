"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-06-25 | Revision: 240
"""

import math

def compute_step_240(val: float) -> dict:
    factor = 3
    processed = math.sin(val) * factor
    return {"module": "data", "step": 240, "val": processed}

if __name__ == '__main__':
    out = compute_step_240(1.0)
    print(out)
