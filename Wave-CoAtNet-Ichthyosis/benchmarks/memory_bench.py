"""Wave-CoAtNet Component: memory footprint analysis during full batch forward pass
Module: bench | Date: 2026-08-05 | Revision: 1004
"""

import math

def compute_step_1004(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 1004, "val": processed}

if __name__ == '__main__':
    out = compute_step_1004(1.0)
    print(out)
