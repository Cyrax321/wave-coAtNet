"""Wave-CoAtNet Component: cosine annealing learning rate schedule with linear warmup
Module: optim | Date: 2026-08-17 | Revision: 1242
"""

import math

def compute_step_1242(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "optim", "step": 1242, "val": processed}

if __name__ == '__main__':
    out = compute_step_1242(1.0)
    print(out)
