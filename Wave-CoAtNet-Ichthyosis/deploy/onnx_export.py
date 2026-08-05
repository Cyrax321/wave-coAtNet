"""Wave-CoAtNet Component: onnx model export with dynamic batch axes support
Module: export | Date: 2026-08-05 | Revision: 1002
"""

import math

def compute_step_1002(val: float) -> dict:
    factor = 17
    processed = math.sin(val) * factor
    return {"module": "export", "step": 1002, "val": processed}

if __name__ == '__main__':
    out = compute_step_1002(1.0)
    print(out)
