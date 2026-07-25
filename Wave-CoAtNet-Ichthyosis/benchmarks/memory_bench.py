"""Wave-CoAtNet Component: memory footprint analysis during full batch forward pass
Module: bench | Date: 2026-07-25 | Revision: 780
"""

import math

def compute_step_780(val: float) -> dict:
    factor = 16
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 780, "val": processed}

if __name__ == '__main__':
    out = compute_step_780(1.0)
    print(out)
