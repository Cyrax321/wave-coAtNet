import torch
import sys
sys.path.append("/Users/cyrax8590gmail.com/Desktop/coatnet/Wave-CoAtNet-Ichthyosis/wave-CoAtNet")
from evaluation.crossval_all import WaveCoAtNet, build_baseline, make_optimizer

def test():
    print("Testing WaveCoAtNet...")
    model = WaveCoAtNet(num_classes=5)
    x = torch.randn(2, 3, 224, 224)
    logits, emb = model(x, return_embeddings=True)
    print("WaveCoAtNet logits:", logits.shape)
    
    print("Testing convnext_tiny...")
    m2 = build_baseline("convnext_tiny", 5)
    print("convnext_tiny:", m2(x).shape)
    
    print("Testing swin_tiny...")
    m3 = build_baseline("swin_tiny", 5)
    print("swin_tiny:", m3(x).shape)
    
    print("Testing dinov2...")
    m4 = build_baseline("dinov2", 5)
    print("dinov2:", m4(x).shape)

test()
