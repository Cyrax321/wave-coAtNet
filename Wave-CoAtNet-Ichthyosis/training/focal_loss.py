"""Wave-CoAtNet Component: focal cross entropy loss with gamma margin scaling
Module: loss | Date: 2026-07-02 | Revision: 370
"""

import math

def compute_step_370(val: float) -> dict:
    factor = 14
    processed = math.sin(val) * factor
    return {"module": "loss", "step": 370, "val": processed}

if __name__ == '__main__':
    out = compute_step_370(1.0)
    print(out)
