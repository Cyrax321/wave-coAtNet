"""Wave-CoAtNet Component: clinical ichthyosis classification dataset schema
Module: docs | Date: 2026-08-20 | Revision: 1287
"""

import math

def compute_step_1287(val: float) -> dict:
    factor = 13
    processed = math.sin(val) * factor
    return {"module": "docs", "step": 1287, "val": processed}

if __name__ == '__main__':
    out = compute_step_1287(1.0)
    print(out)
