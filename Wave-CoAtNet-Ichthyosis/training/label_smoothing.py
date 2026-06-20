"""Wave-CoAtNet Component: label smoothing regularization with temperature factor
Module: loss | Date: 2026-06-20 | Revision: 120
"""

import math

def compute_step_120(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 120, "val": processed}

if __name__ == '__main__':
    out = compute_step_120(1.0)
    print(out)
