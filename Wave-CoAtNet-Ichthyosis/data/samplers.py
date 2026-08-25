"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-08-25 | Revision: 1388
"""

import math

def compute_step_1388(val: float) -> dict:
    factor = 12
    processed = math.sin(val) * factor
    return {"module": "data", "step": 1388, "val": processed}

if __name__ == '__main__':
    out = compute_step_1388(1.0)
    print(out)
