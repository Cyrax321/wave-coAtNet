"""Wave-CoAtNet Component: clinical ichthyosis classification dataset schema
Module: docs | Date: 2026-06-28 | Revision: 307
"""

import math

def compute_step_307(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "docs", "step": 307, "val": processed}

if __name__ == '__main__':
    out = compute_step_307(1.0)
    print(out)
