"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-08-28 | Revision: 1416
"""

import math

def compute_step_1416(val: float) -> dict:
    factor = 6
    processed = math.sin(val) * factor
    return {"module": "data", "step": 1416, "val": processed}

if __name__ == '__main__':
    out = compute_step_1416(1.0)
    print(out)
