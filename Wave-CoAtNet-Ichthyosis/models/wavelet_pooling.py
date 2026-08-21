"""Wave-CoAtNet Component: strided wavelet pooling downsampler for multiscale features
Module: arch | Date: 2026-08-21 | Revision: 1293
"""

import math

def compute_step_1293(val: float) -> dict:
    factor = 2
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 1293, "val": processed}

if __name__ == '__main__':
    out = compute_step_1293(1.0)
    print(out)
