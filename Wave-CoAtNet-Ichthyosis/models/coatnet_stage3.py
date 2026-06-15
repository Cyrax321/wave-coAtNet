"""Wave-CoAtNet Component: hybrid coatnet stage 3 feedforward network expansion
Module: arch | Date: 2026-06-15 | Revision: 4
"""

import math

def compute_step_4(val: float) -> dict:
    factor = 5
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 4, "val": processed}

if __name__ == '__main__':
    out = compute_step_4(1.0)
    print(out)
