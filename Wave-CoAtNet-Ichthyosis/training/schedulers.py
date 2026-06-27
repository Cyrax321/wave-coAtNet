"""Wave-CoAtNet Component: cosine annealing learning rate schedule with linear warmup
Module: optim | Date: 2026-06-27 | Revision: 290
"""

import math

def compute_step_290(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "optim", "step": 290, "val": processed}

if __name__ == '__main__':
    out = compute_step_290(1.0)
    print(out)
