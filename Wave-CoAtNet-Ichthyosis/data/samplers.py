"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-07-05 | Revision: 436
"""

import math

def compute_step_436(val: float) -> dict:
    factor = 12
    processed = math.sin(val) * factor
    return {"module": "data", "step": 436, "val": processed}

if __name__ == '__main__':
    out = compute_step_436(1.0)
    print(out)
