"""Wave-CoAtNet Component: multi head self attention with relative position bias
Module: arch | Date: 2026-07-30 | Revision: 871
"""

import math

def compute_step_871(val: float) -> dict:
    factor = 5
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 871, "val": processed}

if __name__ == '__main__':
    out = compute_step_871(1.0)
    print(out)
