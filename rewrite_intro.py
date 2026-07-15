import re

filepath = '/Users/cyrax8590gmail.com/Desktop/coatnet/extracted_text/Skin_Journal_GEC_Idukki.txt'

with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

new_intro = """1 Introduction
The ichthyoses constitute a highly heterogeneous group of Mendelian disorders of cornification, characterized by widespread, persistent hyperkeratosis, scaling, and profound epidermal barrier dysfunction. Pathogenetically, these genodermatoses are driven by distinct genetic mutations disrupting the epidermal differentiation complex—such as *TGM1* in Lamellar Ichthyosis, *FLG* in Ichthyosis Vulgaris, *SPINK5* in Netherton Syndrome, and *ABCA12* in Harlequin Ichthyosis. Despite these distinct molecular etiologies, the resulting cutaneous phenotypes exhibit extreme morphological overlap. The clinical spectrum ranges from mild, highly prevalent presentations (e.g., Ichthyosis Vulgaris, 1 in 250) to ultra-rare, life-threatening neonatal emergencies requiring immediate intensive care (e.g., Harlequin Ichthyosis, 1 in 300,000). This drastic variance in incidence, coupled with striking visual similarities among distinct genetic entities, establishes ichthyosis classification as a tremendously challenging domain for both clinicians and computational systems.

Current diagnostic workflows rely heavily on subjective clinical evaluation, occasionally supplemented by histopathological examination or protracted genomic sequencing. These paradigms are inherently constrained by inter-observer variability, limited global access to specialized dermatogenetic expertise, and the time-critical nature of neonatal disease management. Consequently, patients frequently endure a protracted "diagnostic odyssey." There is an urgent, unmet clinical need for rapid, automated computational phenotyping systems capable of delivering highly accurate, objective morphological stratification to accelerate targeted therapeutic interventions.

While deep learning—particularly Convolutional Neural Networks (CNNs) and Vision Transformers (ViTs)—has revolutionized the diagnosis of common dermatological malignancies (e.g., melanoma), its translation to rare genodermatoses remains critically underdeveloped. The application of standard AI architectures to ichthyosis classification is impeded by two fundamental bottlenecks: (1) extreme, naturally occurring class imbalances inherent to rare disease epidemiology, and (2) the failure of standard transfer learning from natural image datasets to resolve the subtle, high-frequency textural differentiators (e.g., fine polygonal scaling versus thick, plate-like fissures) that define these specific skin conditions. Conventional networks typically treat these critical micro-textures as high-frequency noise, leading to catastrophic misclassification of rare variants.

Within this landscape, a significant methodological gap exists: the absence of specialized hybrid architectures capable of simultaneously capturing localized pathological micro-textures and global anatomical distributions. We address this fundamental limitation by introducing WaveCoAtNet, an advanced hybrid framework explicitly engineered to resolve the complex morphological overlaps of rare dermatological disorders. By integrating discrete wavelet transforms within a cross-attention mechanism, WaveCoAtNet forcefully decouples macro-structural features from fine textural details, achieving unprecedented state-of-the-art diagnostic accuracy.

1.1 Related Work and Motivation
Current dermatological AI research is overwhelmingly skewed toward melanoma and common inflammatory lesions. Systematic reviews underscore a glaring deficit in the application of advanced computational techniques to rare genetic skin disorders. While recent global initiatives have begun aggregating specialized rare-disease datasets, practical algorithmic implementations remain largely confined to traditional machine learning (e.g., SVMs) or unadapted, off-the-shelf convolutional networks that suffer from severe inductive bias limitations when faced with morphological ambiguity. 

Recent advancements in hybrid architectures demonstrate that combining convolutional inductive biases with transformer-based global receptive fields yields superior feature representations. However, applying these networks directly to ichthyosis fails to explicitly account for the frequency-domain characteristics of the lesions. Distinguishing the subtlest morphological differences—such as the fine, adherent scaling of Ichthyosis Vulgaris versus the deep, geometric fissures of Harlequin Ichthyosis—demands explicit frequency decomposition. This critical observation motivates the core of our WaveCoAtNet architecture: leveraging multi-scale wavelet transforms to enforce frequency-aware attention, thereby ensuring that neither structural morphology nor microscopic texture is suppressed during feature aggregation.

1.2 Major Contributions
This study presents three fundamental contributions to computational dermatology and rare disease diagnostics:
1. **Curated Rare Disease Dataset**: We address the critical data scarcity in rare disease research by compiling, standardizing, and releasing a comprehensive dataset of 2,508 high-resolution images spanning five distinct ichthyosis categories, providing a robust new benchmark for computational phenotyping.
2. **WaveCoAtNet Architecture**: We propose a novel state-of-the-art hybrid network driven by Wavelet-Guided Frequency-Decomposed Cross-Attention (WG-FDCA), Prototype-Anchored Dynamic Token Selection (PA-DTS), and Supervised Contrastive Token Regularization (SCTR). This explicit separation of structural and textural features allows the network to isolate diagnostically critical regions while strictly enforcing inter-class separability.
3. **Comprehensive Benchmarking & SOTA Performance**: Through rigorous 5-fold cross-validation, WaveCoAtNet achieves an exceptional mean accuracy of 96.25% and a macro-average F1-score of 0.9550. In direct evaluations against 11 standard and foundational baselines (including DINOv2 and BiomedCLIP), WaveCoAtNet matches the performance of massive foundation models utilizing up to 6.5× fewer parameters, establishing a new standard for efficient, high-accuracy rare disease classification.

"""

pattern = re.compile(r"1 Introduction\n.*?2 Proposed State-of-the-Art:", re.DOTALL)
new_text = pattern.sub(new_intro + "2 Proposed State-of-the-Art:", text)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Introduction rewritten successfully.")
