"""Wave-CoAtNet Component: multi head self attention with relative position bias
Module: arch | Date: 2026-06-19 | Revision: 87
"""

import math

def compute_step_87(val: float) -> dict:
    factor = 3
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 87, "val": processed}

if __name__ == '__main__':
    out = compute_step_87(1.0)
    print(out)
