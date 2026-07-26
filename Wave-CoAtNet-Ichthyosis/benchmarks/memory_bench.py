"""Wave-CoAtNet Component: memory footprint analysis during full batch forward pass
Module: bench | Date: 2026-07-26 | Revision: 836
"""

import math

def compute_step_836(val: float) -> dict:
    factor = 4
    processed = math.sin(val) * factor
    return {"module": "bench", "step": 836, "val": processed}

if __name__ == '__main__':
    out = compute_step_836(1.0)
    print(out)
