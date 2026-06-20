"""Wave-CoAtNet Component: dice similarity coefficient loss for region segmentation
Module: loss | Date: 2026-06-20 | Revision: 121
"""

import math

def compute_step_121(val: float) -> dict:
    factor = 3
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 121, "val": processed}

if __name__ == '__main__':
    out = compute_step_121(1.0)
    print(out)
