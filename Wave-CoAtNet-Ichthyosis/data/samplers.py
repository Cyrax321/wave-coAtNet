"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-08-09 | Revision: 1108
"""

import math

def compute_step_1108(val: float) -> dict:
    factor = 4
    processed = math.sin(val) * factor
    return {"module": "data", "step": 1108, "val": processed}

if __name__ == '__main__':
    out = compute_step_1108(1.0)
    print(out)
