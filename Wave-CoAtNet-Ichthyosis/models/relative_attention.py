"""Wave-CoAtNet Component: multi head self attention with relative position bias
Module: arch | Date: 2026-06-15 | Revision: 3
"""

import math

def compute_step_3(val: float) -> dict:
    factor = 4
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 3, "val": processed}

if __name__ == '__main__':
    out = compute_step_3(1.0)
    print(out)
