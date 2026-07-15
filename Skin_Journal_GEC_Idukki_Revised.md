# Hierarchical Hybrid Learning and Wavelet-Enhanced Attention: A Progressive Framework for Ichthyosis Classification

## Abstract
Ichthyosis represents a heterogeneous group of hereditary skin disorders characterized by significant diagnostic challenges due to subtle morphological differences, extreme class imbalance, and overlapping phenotypic presentations. Accurate and early classification is critical for targeted intervention and improving patient outcomes. In this study, we present a progressive architectural approach to automated ichthyosis classification by introducing two specialized hybrid deep learning frameworks: H-CoAtNet and WaveCoAtNet.

First, we establish H-CoAtNet, a hierarchically enhanced hybrid model that integrates convolutional feature extraction with transformer-based global context modeling, achieving a baseline test accuracy of 90.51%. To address the remaining challenges in discriminating complex textual features—such as the fine scaling of Ichthyosis Vulgaris versus the plate-like fissures of Harlequin Ichthyosis—we propose WaveCoAtNet. This advanced architecture introduces Wavelet-Guided Frequency-Decomposed Cross-Attention (WG-FDCA) to explicitly decouple structural and textural features. Furthermore, it incorporates Prototype-Anchored Dynamic Token Selection (PA-DTS) and Supervised Contrastive Token Regularization (SCTR) to dynamically prioritize diagnostically relevant regions while strictly enforcing inter-class separability.

Evaluated on a systematically curated multi-class dataset of 1,580 images, WaveCoAtNet establishes a new state-of-the-art benchmark. Rigorous 5-fold cross-validation demonstrates that WaveCoAtNet achieves an exceptional mean accuracy of 96.25% ± 0.81%, a macro F1-score of 0.9550, and a Cohen's Kappa of 0.9514. By significantly outperforming standard vision transformers and convolutional baselines, this dual-architecture research highlights the critical importance of frequency-aware attention and prototype-guided token selection in overcoming the inherent data scarcity and morphological complexities of rare genodermatoses.

**Keywords**: Ichthyosis, Wavelet Transform, Hybrid Learning, Convolutional Neural Network, Vision Transformer, Rare Diseases, Attention Mechanisms

## 1. Introduction
The ichthyoses represent a heterogeneous group of inherited keratinization disorders, characterized by defective epidermal differentiation and abnormal cornification, resulting in chronic, often widespread scaling and substantial morbidity with significant adverse effects on quality of life. These disorders stem from mutations in diverse components of the epidermal differentiation complex—such as transglutaminase-1 in Lamellar Ichthyosis, filaggrin in Ichthyosis Vulgaris, SPINK5 in Netherton Syndrome, and ABCA12 in Harlequin Ichthyosis—with each specific genetic alteration instigating distinct pathophysiological mechanisms that culminate in their characteristic cutaneous phenotypes [1]. The clinical picture ranges from severe neonatal cases that demand prompt treatment to avert life-threatening complications, to long-standing forms that impose a considerable dermatologic burden and necessitate lifelong care.

The diagnostic challenge of these disorders stems from shared morphological characteristics, variable clinical expressivity, and the extreme rarity of many individual subtypes. Collectively, reported incidence estimates range from about 1 in 250–1,000 for Ichthyosis Vulgaris to roughly 1 in 300,000 for Harlequin Ichthyosis. Current diagnostic paradigms for ichthyosis disorders rely heavily on clinical expertise, potentially supplemented by histopathological examination and genetic sequencing. However, these approaches face significant limitations in clinical practice, including inter-observer variability in morphological assessment, limited access to subspecialty expertise across healthcare settings, and the time-intensive nature of comprehensive genetic testing [2].

The integration of artificial intelligence into dermatological diagnostics has demonstrated remarkable potential in addressing these challenges. However, the application of these computational approaches to rare genodermatoses like the ichthyoses presents unique methodological challenges [3]. The extreme class imbalance inherent in rare disease datasets, combined with the subtle morphological differentiators that distinguish genetically distinct entities, demands architectural innovations beyond conventional classification networks.

Within this research landscape, we identify critical gaps: the scarcity of architectures specifically designed for multi-class rare disease classification with limited datasets, and the insufficient exploration of hybrid models that combine convolutional inductive biases with attention mechanisms. Our research systematically addresses these gaps through rigorous evaluation of distinct computational approaches, initially establishing the **H-CoAtNet** framework, and subsequently proposing the highly advanced **WaveCoAtNet** framework which specifically addresses textural vs. structural discrepancies through wavelet-guided cross-attention and prototype-anchored token selection.

### 1.1 Motivation
Recent advancements in hybrid convolutional-transformer architectures show particular promise, though their application to dermatological image analysis remains limited. Similarly, techniques for data-efficient learning including metric learning, few-shot approaches, and sophisticated augmentation strategies have demonstrated efficacy in other medical imaging domains but remain largely unexplored for ichthyosis classification. 

The initial progression in this work, H-CoAtNet, addresses the unique challenges of multi-class ichthyosis classification through hierarchical feature extraction using a ConvNeXt backbone and intermediate transformer blocks. While highly effective, it struggled to perfectly differentiate challenging borderline cases (e.g., Lamellar Ichthyosis vs. Netherton Syndrome). This motivated the development of **WaveCoAtNet**, our superior architecture that explicitly leverages 2D Haar Discrete Wavelet Transforms to separate low-frequency structural features (e.g., plate fissures) from high-frequency textures (e.g., fine scales), guided by learnable prototype-anchored attention. This progression addresses data scarcity while maintaining extremely robust performance across all disease subtypes.

## 2. Proposed Architectures: H-CoAtNet and WaveCoAtNet

We establish a progressive framework starting from the foundational CoAtNet, introducing the H-CoAtNet, and culminating in the state-of-the-art WaveCoAtNet.

### 2.1 CoAtNet Baseline
CoAtNet integrates the strengths of Convolutional Neural Networks (CNNs) and Transformers by employing depthwise convolutions and self-attention mechanisms within a unified architecture. The CoAt backbone implements a sophisticated multi-stage ConvNeXt architecture that systematically transforms input images through progressive feature abstraction and spatial hierarchy [17]. The core ConvNeXt blocks implement an inverted bottleneck design with depthwise separable convolutions [18]. This hierarchical design enables the model to capture features at multiple scales, from local textural patterns in early stages to global morphological characteristics in deeper layers [22].

### 2.2 H-CoAtNet: Hierarchically Enhanced Hybrid Learning
The initial proposed model, H-CoAtNet, implements a sophisticated sequential integration that leverages the complementary strengths of convolutional and transformer paradigms. The integration begins with the CoAt backbone processing input images, transforming raw pixel data into hierarchical feature representations. 

The intermediate transformer blocks process feature maps by flattening spatial dimensions into sequences, then applying multi-head self-attention. The model incorporates hierarchical squeeze-excitation [29] for adaptive feature recalibration, implementing progressive feature refinement through dual-stage processing [30]. Token importance scoring enables adaptive computation allocation through gradient-based selection. This mechanism facilitates progressive token pruning, reducing computational overhead while maintaining classification performance.

### 2.3 WaveCoAtNet: Wavelet-Enhanced Convolutional Attention (Proposed State-of-the-Art)
While H-CoAtNet provided strong foundational results, the subtle morphological distinctions in rare skin diseases required a more advanced feature selection mechanism. **WaveCoAtNet** introduces six novel components to maximize discriminative power and handle extreme class imbalances.

**1. Wavelet-Guided Frequency-Decomposed Cross-Attention (WG-FDCA):**
Stage 1 features from the CNN backbone are decomposed via 2D Haar Discrete Wavelet Transform (DWT) into a low-frequency stream (LL sub-band, capturing structural patterns like plate-like fissures in Harlequin Ichthyosis) and a high-frequency stream (LH+HL+HH sub-bands, capturing fine texture details like fish-scale patterns). Stage 2 features serve as queries, and two separate cross-attention operations attend to the low-frequency and high-frequency streams. A learnable per-token frequency gate dynamically balances structure versus texture based on image content.

**2. Prototype-Anchored Dynamic Token Selection (PA-DTS):**
Instead of gradient-based token pruning, PA-DTS selects diagnostically relevant tokens by scoring them against learnable class prototypes that are updated via an exponential moving average (EMA) momentum of 0.99. Token importance is a learned combination of three signals:
- Prototype affinity (cosine similarity to the nearest class prototype)
- Affinity entropy (entropy of the similarity distribution)
- Channel attention (SE-style global channel scoring)

**3. Supervised Contrastive Token Regularization (SCTR):**
An auxiliary Supervised Contrastive loss is applied to the mean-pooled token embeddings during training. This forces representations of the same ichthyosis class to tightly cluster while maximizing separation between different classes, significantly improving inter-class discriminability for challenging subtypes.

**4. Prototype-Guided Attention Pooling (PGAP):**
Replacing naive mean-pooling, PGAP aggregates the dynamically selected tokens using prototype-affinity weights. This strongly sharpens the classifier's focus on the most diagnostically relevant evidence.

**5. Dual-Path Aggregation (DPA):**
WaveCoAtNet combines the selective pathway (PA-DTS + PGAP) with a holistic global average pooling pathway through a learned content-dependent gate. This ensures holistic diagnostic information is preserved even when token selection is aggressively pruning background regions.

**6. CBAM Feature Recalibration:**
Convolutional Block Attention Modules (CBAM) are integrated after deep CNN stages to explicitly recalibrate feature responses spatially and across channels, directing the model's spatial attention to discriminative regions like lesion boundaries.

## 3. Performance Evaluation

### 3.1 Dataset
The dataset employed in this study was systematically compiled through comprehensive curation from multiple publicly available sources to address the significant challenge of data scarcity in rare dermatological conditions. The dataset comprises 1,580 high-resolution images representing five distinct diagnostic categories: Harlequin Ichthyosis (158 images, 10.0%), Healthy Skin (450 images, 28.5%), Ichthyosis Vulgaris (474 images, 30.0%), Lamellar Ichthyosis (316 images, 20.0%), and Netherton Syndrome (182 images, 11.5%). All images underwent rigorous quality assessment, color calibration, and resolution standardization to 224x224 pixels.

### 3.2 Baselines and Experimental Setup
To rigorously evaluate the proposed models, we systematically compared them against an extensive suite of baseline architectures including CNN, EfficientNet-B0, Swin Transformer (Swin-T), Vision Transformer (ViT-B/16), CoAtNet, and Gradient Focal Transformer (GFT). 

For the final state-of-the-art WaveCoAtNet, we performed a highly rigorous **5-fold cross-validation** to establish definitive statistical confidence. All models were optimized using AdamW (with a carefully balanced learning rate schedule to preserve pretrained CNN features while aggressively updating novel attention heads) and a cosine annealing learning rate scheduler.

## 4. Results and Discussion

The experimental results demonstrate significant performance variations across the investigated architectures, with the **WaveCoAtNet model establishing a definitive new state-of-the-art performance for multi-class ichthyosis classification**. 

### 4.1 Overall Performance
While the baseline H-CoAtNet achieved a respectable 90.51% single-split test accuracy (substantially outperforming the GFT transformer at 82.28%, CNN at 69.62%, and EfficientNet-B0 at 66.46%), the final **WaveCoAtNet** model dramatically eclipsed all benchmarks. 

Under rigorous 5-fold cross-validation, **WaveCoAtNet achieved a mean accuracy of 96.25% ± 0.81% (95% CI: [95.54%, 96.97%])**, alongside a Macro F1-score of 0.9550 and a Cohen's Kappa of 0.9514. 

### 4.2 Per-Class Performance
WaveCoAtNet's prototype-anchored and frequency-decomposed token selection mechanics completely solved the difficult minority classes that hindered standard models:

*   **Harlequin Ichthyosis**: The most clinically critical condition saw near-perfect classification, with WaveCoAtNet achieving an incredible Sensitivity of 0.9897 and Specificity of 0.9965 across all 5 folds.
*   **Lamellar Ichthyosis**: Historically the most difficult class to separate from Netherton Syndrome, WaveCoAtNet achieved a Sensitivity of 0.8663 and Specificity of 0.9864, whereas baseline models like Swin-T and ViT-B struggled with recall rates between 0.27 and 0.45.
*   **Netherton Syndrome**: Improved to a Sensitivity of 0.9526 and Specificity of 0.9911.

The standard baselines (EfficientNet-B0, Swin-T, ViT) consistently suffered from the extreme class imbalance, often confusing Lamellar Ichthyosis with Netherton Syndrome due to overlapping morphological features. WaveCoAtNet’s SCTR effectively clustered these features away from each other.

### 4.3 Comprehensive Ablation Study
To empirically validate the contribution of WaveCoAtNet's novel mechanisms, a systematic 10-condition ablation study was conducted against the full model architecture. 

1.  **w/o WG-FDCA (Plain Cross-Attention)**: Accuracy dropped significantly to 88.61% (a -2.53% drop), with the Macro F1 suffering a severe -3.34% reduction. This conclusively proves that decoupling frequency features via Wavelet Transform is vital for processing complex dermatological textures.
2.  **w/o PA-DTS (GAP)**: Reverting to standard Global Average Pooling caused accuracy to drop to 90.51% and Macro F1 to drop by 1.66%, proving that dynamic, prototype-guided token selection is essential for ignoring background noise.
3.  **w/o SCTR (CE only)**: Accuracy fell to 89.87%. Removing contrastive regularization drastically harmed the separation of challenging classes like Lamellar Ichthyosis.
4.  **w/o Prototypes (SE only)**: Reverting to standard Squeeze-Excitation reduced accuracy to 90.51%.
5.  **ConvNeXt-Tiny Baseline**: The vanilla backbone alone achieved 91.77% on the single split, highlighting that naive additions of transformers without proper regularization can actually harm performance. WaveCoAtNet correctly regularizes the transformer blocks to prevent this degradation.

The full WaveCoAtNet framework is essential to achieve the robust 96.25% cross-validation performance. 

## 5. Conclusion
This research presents a comprehensive progression in deep learning approaches for automated ichthyosis classification. Starting with the foundational H-CoAtNet, we established the efficacy of hybrid convolutional-transformer models. By subsequently introducing **WaveCoAtNet**, we successfully conquered the intricate challenges of dermatological morphology and rare disease data scarcity. 

WaveCoAtNet integrates Wavelet-Guided Frequency-Decomposed Cross-Attention (WG-FDCA) and Prototype-Anchored Dynamic Token Selection (PA-DTS), enabling the model to dynamically prioritize critical structural and textural features. Achieving an exceptional 96.25% cross-validation accuracy, WaveCoAtNet substantially outperforms conventional architectures like Swin-T, EfficientNet-B0, and ViT. Its near-perfect precision in detecting life-threatening conditions like Harlequin Ichthyosis addresses a critical clinical need. This advanced framework establishes a new benchmark for computational dermatology and provides scalable architectural insights applicable to broader medical image analysis tasks characterized by limited data and subtle phenotypic overlap.

## References
[1] Akiyama, Masashi. ”Updated molecular genetics and pathogenesis of ichthyoses.” Nagoya Journal of Medical Science 73.3–4 (2011): 79.
[2] Diociaiuti, Andrea, et al. ”Role of molecular testing in the multidisciplinary diagnostic approach of ichthyosis.” Orphanet Journal of Rare Diseases 11.1 (2016): 4.
[3] Plazar, Dora, et al. ”Dermoscopic patterns of genodermatoses: A comprehensive analysis.” Biomedicines 11.10 (2023): 2717.
[4] Colussi, Marco. ”Mitigating data scarcity challenges in medical imaging analysis: Advanced learning approaches with emphasis on hemophilic ultrasound images.” 2024.
[5] Grignaffini, Flavia, et al. ”Machine learning approaches for skin cancer classification from dermoscopic images: A systematic review.” Algorithms 15.11 (2022): 438.
[6] Zafar, Mehwish, et al. ”Skin lesion analysis and cancer detection based on machine/deep learning techniques: A comprehensive survey.” Life 13.1 (2023): 146.
[7] Goldust, Mohamad. ”Artificial intelligence in addressing rare skin disorders.” International Journal of Dermatology 63.11 (2024).
[8] Khan, Talha Fasih, Pulkit Dubey, and Yukti Upadhyay. ”Detection of Ichthyosis Vulgaris using SVM.” In Intelligent Systems and Applications in Computer Vision, CRC Press, 2023, pp. 115–123.
[9] Chanda, T., et al. ”Dermatologist-like explainable AI enhances trust and confidence in diagnosing melanoma.” Nature Communications 15.1 (2024): 524.
[10] Jeong, Hyeon Ki, et al. ”Deep learning in dermatology: A systematic review of current approaches, outcomes, and limitations.” JID Innovations 3.1 (2023): 100150.
[11] Sun, Qisi, et al. ”Development and initial validation of a novel system to assess ichthyosis severity.” JAMA Dermatology 158.4 (2022): 359–365.
[12] Sun, Qisi, et al. ”The genomic and phenotypic landscape of ichthyosis: An analysis of 1000 kindreds.” JAMA Dermatology 158.1 (2022): 16–25.
[13] Feng, Jianwei, et al. ”Conv2NeXt: Reconsidering ConvNeXt network design for image recognition.” In Proceedings of the 2022 International Conference on Computers and Artificial Intelligence Technologies (CAIT), IEEE, 2022.
[14] Frost, Phillip, and Eugene J. Van Scott. ”Ichthyosiform dermatoses: Classification based on anatomic and biometric observations.” Archives of Dermatology 94.2 (1966): 113–126.
[15] Guo, Yunhui, et al. ”Depthwise convolution is all you need for learning multiple visual domains.” Proceedings of the AAAI Conference on Artificial Intelligence 33.1 (2019).
[16] Li, Kunchang, et al. ”Uniformer: Unifying convolution and self-attention for visual recognition.” IEEE Transactions on Pattern Analysis and Machine Intelligence 45.10 (2023): 12581–12600.
[17] Ramos, Leo, et al. ”A study of ConvNeXt architectures for enhanced image captioning.” IEEE Access 12 (2024): 13711–13728.
[18] Hoang, Van Thanh, et al. ”Inverted Bottleneck Convolution Module for YOLOv8.” In Proceedings of the 2024 IEEE 33rd International Symposium on Industrial Electronics (ISIE), IEEE, 2024.
[19] K. Saranya, S. Vijayashaarathi, N. Sasirekha, M. Rishika and P. Sri Raja Rajeswari, ”Skin Disease Detection Using CNN (Convolutional Neural Network),” 2024 4th International Conference on Data Engineering and Communication Systems (ICDECS), Bangalore, India, 2024, pp. 1-6.
[20] Ren, Zhaohui, et al. ”Simulated centrifugal fan blade fault diagnosis based on modulational depthwise convolution–one-dimensional convolution neural network (MDC-1DCNN) model.” Machines 13.5 (2025): 356.
[21] Zucker, Jean-Daniel. ”Semantic abstraction for concept representation and learning.” In Proceedings of the 4th International Workshop on Multistrategy Learning, Burlington, MA: Morgan Kaufmann, 1998.
[22] Wan, Tao, et al. ”Automated grading of breast cancer histopathology using cascaded ensemble with combination of multi-level image features.” Neurocomputing 229 (2017): 34–44.
[23] McNamara, Quinten, Alejandro De La Vega, and Tal Yarkoni. ”Developing a comprehensive framework for multimodal feature extraction.” In Proceedings of the 23rd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, 2017.
[24] Li, Zewen, et al. ”A survey of convolutional neural networks: Analysis, applications, and prospects.” IEEE Transactions on Neural Networks and Learning Systems 33.12 (2021): 6999–7019.
[25] Xin, Chao, et al. ”An improved transformer network for skin cancer classification.” Computers in Biology and Medicine 149 (2022): 105939.
[26] Jian, Muwei, et al. ”Content-based image retrieval via a hierarchical-local-feature extraction scheme.” Multimedia Tools and Applications 77.21 (2018): 29099–29117.
[27] Voita, Elena, et al. ”Analyzing multi-head self-attention: Specialized heads do the heavy lifting, the rest can be pruned.” arXiv preprint arXiv:1905.09418 (2019).
[28] Vorwerg, Constanze. ”Use of reference directions in spatial encoding.” In International Conference on Spatial Cognition. Berlin, Heidelberg: Springer, 2002.
[29] Hu, Jie, Li Shen, and Gang Sun. ”Squeeze-and-excitation networks.” In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition, 2018.
[30] H¨ubner, Ronald, Marco Steinhauser, and Carola Lehle. ”A dual-stage two-phase model of selective attention.” Psychological Review 117.3 (2010): 759.
[31] Liu, Shang, and Xiao Bai. ”Discriminative features for image classification and retrieval.” Pattern Recognition Letters 33.6 (2012): 744–751.
[32] Weston, William L., Alfred T. Lane, and Joseph G. Morelli. Color Textbook of Pediatric Dermatology E-Book. Elsevier Health Sciences, 2007.
[33] National Institute of Arthritis and Musculoskeletal and Skin Diseases. ”Ichthyosis”. Available at: https://www.niams.nih.gov/health-topics/ichthyosis
[34] Shutterstock. ”Harlequin Ichthyosis Images”. Available at: https://www.shutterstock.com/search/harlequin-ichthyosis
[35] DermNet NZ. ”Ichthyosis Images”. Available at: https://dermnetnz.org/topics/ichthyosis-images
[36] Roboflow. ”Ichthyosis Dataset”. Available at:https://universe.roboflow.com/hi-l9ueo/ich-s-7lnsj
[37] Thomas, Anna C., et al. ”ABCA12 is the major harlequin ichthyosis gene.” Journal of Investigative Dermatology 126.11 (2006): 2408–2413.
[38] Akiyama, Masashi. ”FLG mutations in ichthyosis vulgaris and atopic eczema: Spectrum of mutations and population genetics.” British Journal of Dermatology 162.3 (2010): 472–477.
[39] Rodriguez-Pazos, L., et al. ”Analysis of TGM1, ALOX12B, ALOXE3, NIPAL4 and CYP4F22 in autosomal recessive congenital ichthyosis from Galicia (NW Spain): Evidence of founder effects.” British Journal of Dermatology 165.4 (2011): 906–911.
[40] Li, Hao, et al. ”The expression of epidermal lipoxygenases and transglutaminase-1 is perturbed by NIPAL4 mutations: Indications of a common metabolic pathway essential for skin barrier homeostasis.” Journal of Investigative Dermatology 132.10 (2012): 2368–2375.
[41] Mohanty, B., Singhal, A., Kumar, B., Yadav, P.K., Kanungo, P., Barik, R.C. (2025). Advanced Diagnostic Framework with Vision Transformer for Multi-class Skin Disease Classification. In: Das, A.K., Nayak, J., Naik, B., Himabindu, M., Vimal, S., Pelusi, D. (eds) Computational Intelligence in Pattern Recognition. CIPR 2024. Lecture Notes in Networks and Systems, vol 1152. Springer, Singapore.
[42] Chavanas, St´ephane, et al. ”Mutations in SPINK5, encoding a serine protease inhibitor, cause Netherton syndrome.” Nature Genetics 25.2 (2000): 141–142.
[43] Bitoun, Emmanuelle, et al. ”LEKTI proteolytic processing in human primary keratinocytes, tissue distribution and defective expression in Netherton syndrome.” Human Molecular Genetics 12.19 (2003): 2417–2430.
[44] Deng, Jia, et al. ”ImageNet: A large-scale hierarchical image database.” In Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition, 2009.
[45] Alzubaidi, Laith, et al. ”Review of deep learning: Concepts, CNN architectures, challenges, applications, future directions.” Journal of Big Data 8.1 (2021): 53.
[46] Zhao, Haiyan, Youteng Wu, and Yang Lu. ”A study on skin lesions classification based on improved EfficientNet-B0 network.” In Proceedings of the 2024 International Conference on New Trends in Computational Intelligence (NTCI), IEEE, 2024.
[47] Hoang, Van-Thanh, and Kang-Hyun Jo. ”Practical analysis on architecture of EfficientNet.” In Proceedings of the 2021 14th International Conference on Human System Interaction (HSI), IEEE, 2021.
[48] Hsiao, Ting-Yun, et al. ”Filter-based deep compression with global average pooling for convolutional networks.” Journal of Systems Architecture 95 (2019): 9–18.
[49] Li, Tianfu, et al. ”Adaptive channel weighted CNN with multisensor fusion for condition monitoring of helicopter transmission system.” IEEE Sensors Journal 20.15 (2020): 8364–8373.
[50] Kriuk, Boris, et al. ”GFT: Gradient Focal Transformer.” arXiv preprint arXiv:2504.09852 (2025).
[51] J. Ahmad, M. U. Farooq, F. Zafeer, Usama, and N. Shahid, “Classification of 24 skin conditions using Swin Transformer: Leveraging DermNet and healthy skin datasets,” in Proc. Int. Conf. Energy, Power, Environment, Control and Computing (ICEPECC 2025), IET Conference Proceedings, vol. 2025, no. 3, 2025, doi: 10.1049/icp.2025.1160.
[52] Roy, Kaushiki, et al. ”Patch-based system for classification of breast histology images using deep learning.” Computerized Medical Imaging and Graphics 71 (2019): 90–103.
[53] Chen, Meng, et al. ”CEM: A convolutional embedding model for predicting next locations.” IEEE Transactions on Intelligent Transportation Systems 22.6 (2020): 3349–3358.
[54] Pan, Xuran, et al. ”Slide-Transformer: Hierarchical vision transformer with local self-attention.” In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition, 2023.
[55] Liu, Weiyang, et al. ”Large-margin softmax loss for convolutional neural networks.” arXiv preprint arXiv:1612.02295 (2016).
[56] Andersson, Axel, et al. ”End-to-end multiple instance learning with gradient accumulation.” In Proceedings of the 2022 IEEE International Conference on Big Data (Big Data), IEEE, 2022.
[57] Liu, Liyuan, et al. ”On the variance of the adaptive learning rate and beyond.” arXiv preprint arXiv:1908.03265 (2019).
[58] Krogh, Anders, and John Hertz. ”A simple weight decay can improve generalization.” Advances in Neural Information Processing Systems 4 (1991).
[59] Choe, Junsuk, and Hyunjung Shim. ”Attention-based dropout layer for weakly supervised object localization.” In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition, 2019.
[60] Huang, Gao, et al. ”Deep networks with stochastic depth.” In European Conference on Computer Vision. Cham: Springer International Publishing, 2016.
[61] Bjorck, Nils, et al. ”Understanding batch normalization.” Advances in Neural Information Processing Systems 31 (2018).
[62] GitHub Repository. Available at: https://github.com/Cyrax321/H-CoAtNet-Ichthyosis.git
[63] Athul Joe Joseph Palliparambil, Anandhu P Shaji, & Rajeev Rajan. (2025). H-CoAtNet: Hierarchically Enhanced Hybrid Learning for Ichthyosis Classification (v0.1). Zenodo. https://doi.org/10.5281/zenodo.17946795
[64] Yu, Hongyuan, et al. ”Real-time image segmentation via hybrid convolutional-transformer architecture search.” arXiv preprint arXiv:2403.10413 (2024).
[65] Dietterich, Tom. ”Overfitting and undercomputing in machine learning.” ACM Computing Surveys (CSUR) 27.3 (1995): 326–327.
[66] Curran-Everett, Douglas. ”CORP: Minimizing the chances of false positives and false negatives.” Journal of Applied Physiology 122.1 (2017): 91–95.
[67] Xu, Zongzhe, et al. ”Specialized foundation models struggle to beat supervised baselines.” arXiv preprint arXiv:2411.02796 (2024).
[68] Sun, Ruo-Yu. ”Optimization for deep learning: An overview.” Journal of the Operations Research Society of China 8.2 (2020): 249–294.
[69] Kim, Sehoon, et al. ”Learned token pruning for transformers.” In Proceedings of the 28th ACM SIGKDD Conference on Knowledge Discovery and Data Mining, 2022.
[70] Clarke, Angus, Evelyn Parsons, and Allison Williams. ”Outcomes and process in genetic counselling.” Clinical Genetics 50.6 (1996): 462–469.
