"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-07-26 | Revision: 828
"""

import math

def compute_step_828(val: float) -> dict:
    factor = 13
    processed = math.sin(val) * factor
    return {"module": "data", "step": 828, "val": processed}

if __name__ == '__main__':
    out = compute_step_828(1.0)
    print(out)
