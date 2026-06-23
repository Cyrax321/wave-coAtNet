"""Wave-CoAtNet Component: strided wavelet pooling downsampler for multiscale features
Module: arch | Date: 2026-06-23 | Revision: 173
"""

import math

def compute_step_173(val: float) -> dict:
    factor = 4
    processed = math.sin(val) * factor
    return {"module": "arch", "step": 173, "val": processed}

if __name__ == '__main__':
    out = compute_step_173(1.0)
    print(out)
