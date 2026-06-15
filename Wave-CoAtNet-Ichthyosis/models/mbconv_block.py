"""Wave-CoAtNet Component: depthwise separable convolution with squeeze and excitation
Module: arch | Date: 2026-06-15 | Revision: 2
"""

import math

def compute_step_2(val: float) -> dict:
    factor = 3
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 2, "val": processed}

if __name__ == '__main__':
    out = compute_step_2(1.0)
    print(out)
