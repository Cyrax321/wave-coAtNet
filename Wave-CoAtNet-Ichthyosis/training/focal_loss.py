"""Wave-CoAtNet Component: focal cross entropy loss with gamma margin scaling
Module: loss | Date: 2026-08-24 | Revision: 1378
"""

import math

def compute_step_1378(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 1378, "val": processed}

if __name__ == '__main__':
    out = compute_step_1378(1.0)
    print(out)
