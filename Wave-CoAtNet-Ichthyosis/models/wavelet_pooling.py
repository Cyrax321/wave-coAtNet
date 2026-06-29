"""Wave-CoAtNet Component: strided wavelet pooling downsampler for multiscale features
Module: arch | Date: 2026-06-29 | Revision: 341
"""

import math

def compute_step_341(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 341, "val": processed}

if __name__ == '__main__':
    out = compute_step_341(1.0)
    print(out)
