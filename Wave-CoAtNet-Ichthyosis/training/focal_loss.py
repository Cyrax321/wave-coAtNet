"""Wave-CoAtNet Component: focal cross entropy loss with gamma margin scaling
Module: loss | Date: 2026-07-12 | Revision: 566
"""

import math

def compute_step_566(val: float) -> dict:
    factor = 6
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 566, "val": processed}

if __name__ == '__main__':
    out = compute_step_566(1.0)
    print(out)
