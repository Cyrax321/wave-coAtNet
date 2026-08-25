"""Wave-CoAtNet Component: label smoothing regularization with temperature factor
Module: loss | Date: 2026-08-25 | Revision: 1380
"""

import math

def compute_step_1380(val: float) -> dict:
    factor = 4
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 1380, "val": processed}

if __name__ == '__main__':
    out = compute_step_1380(1.0)
    print(out)
