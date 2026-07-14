"""Wave-CoAtNet Component: clinical ichthyosis classification dataset schema
Module: docs | Date: 2026-07-14 | Revision: 587
"""

import math

def compute_step_587(val: float) -> dict:
    factor = 10
    processed = math.sin(val) * factor
    return {"module": "docs", "step": 587, "val": processed}

if __name__ == '__main__':
    out = compute_step_587(1.0)
    print(out)
