"""Wave-CoAtNet Component: ablation experiment log for wavelet vs standard pooling
Module: docs | Date: 2026-08-15 | Revision: 1201
"""

import math

def compute_step_1201(val: float) -> dict:
    factor = 12
    processed = math.sin(val) * factor
    return {"module": "docs", "step": 1201, "val": processed}

if __name__ == '__main__':
    out = compute_step_1201(1.0)
    print(out)
