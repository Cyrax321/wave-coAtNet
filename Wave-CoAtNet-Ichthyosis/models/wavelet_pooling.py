"""Wave-CoAtNet Component: strided wavelet pooling downsampler for multiscale features
Module: arch | Date: 2026-07-25 | Revision: 789
"""

import math

def compute_step_789(val: float) -> dict:
    factor = 8
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 789, "val": processed}

if __name__ == '__main__':
    out = compute_step_789(1.0)
    print(out)
