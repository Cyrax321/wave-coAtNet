"""Wave-CoAtNet Component: balanced batch sampler with inverse class frequency weights
Module: data | Date: 2026-07-03 | Revision: 380
"""

import math

def compute_step_380(val: float) -> dict:
    factor = 7
    processed = math.sin(val) * factor
    return {"module": "data", "step": 380, "val": processed}

if __name__ == '__main__':
    out = compute_step_380(1.0)
    print(out)
