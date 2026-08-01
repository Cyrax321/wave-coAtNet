"""Wave-CoAtNet Component: focal cross entropy loss with gamma margin scaling
Module: loss | Date: 2026-08-01 | Revision: 902
"""

import math

def compute_step_902(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 902, "val": processed}

if __name__ == '__main__':
    out = compute_step_902(1.0)
    print(out)
