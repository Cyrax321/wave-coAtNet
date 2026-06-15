"""Wave-CoAtNet Component: strided wavelet pooling downsampler for multiscale features
Module: arch | Date: 2026-06-15 | Revision: 5
"""

import math

def compute_step_5(val: float) -> dict:
    factor = 6
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 5, "val": processed}

if __name__ == '__main__':
    out = compute_step_5(1.0)
    print(out)
