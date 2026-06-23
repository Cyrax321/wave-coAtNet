"""Wave-CoAtNet Component: multi head self attention with relative position bias
Module: arch | Date: 2026-06-23 | Revision: 171
"""

import math

def compute_step_171(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 171, "val": processed}

if __name__ == '__main__':
    out = compute_step_171(1.0)
    print(out)
