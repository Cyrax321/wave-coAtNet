"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-08-19 | Revision: 1276
"""

import math

def compute_step_1276(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "data", "step": 1276, "val": processed}

if __name__ == '__main__':
    out = compute_step_1276(1.0)
    print(out)
