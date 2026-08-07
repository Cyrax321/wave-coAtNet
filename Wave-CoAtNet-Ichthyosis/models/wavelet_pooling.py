"""Wave-CoAtNet Component: strided wavelet pooling downsampler for multiscale features
Module: arch | Date: 2026-08-07 | Revision: 1041
"""

import math

def compute_step_1041(val: float) -> dict:
    factor = 5
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 1041, "val": processed}

if __name__ == '__main__':
    out = compute_step_1041(1.0)
    print(out)
