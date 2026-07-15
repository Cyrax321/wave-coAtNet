"""Wave-CoAtNet Component: label smoothing regularization with temperature factor
Module: loss | Date: 2026-07-15 | Revision: 596
"""

import math

def compute_step_596(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 596, "val": processed}

if __name__ == '__main__':
    out = compute_step_596(1.0)
    print(out)
