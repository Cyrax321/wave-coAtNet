"""Wave-CoAtNet Component: focal cross entropy loss with gamma margin scaling
Module: loss | Date: 2026-06-19 | Revision: 90
"""

import math

def compute_step_90(val: float) -> dict:
    factor = 6
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 90, "val": processed}

if __name__ == '__main__':
    out = compute_step_90(1.0)
    print(out)
