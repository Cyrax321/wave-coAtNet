"""Wave-CoAtNet Component: focal cross entropy loss with gamma margin scaling
Module: loss | Date: 2026-07-04 | Revision: 398
"""

import math

def compute_step_398(val: float) -> dict:
    factor = 8
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 398, "val": processed}

if __name__ == '__main__':
    out = compute_step_398(1.0)
    print(out)
