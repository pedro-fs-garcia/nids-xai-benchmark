# Bibliography

References for the study of TreeSHAP execution strategies and latency in a Network Intrusion Detection System (NIDS).

## Local article documents

Each article below links directly to its Markdown transcription in this directory. The transcriptions preserve the source wording and language; their figures are stored in `assets/`.

| Authors | Article document | Relevance to the project |
|---|---|---|
| Richard Zuech, Taghi M. Khoshgoftaar, and Randall Wald | [Intrusion Detection and Big Heterogeneous Data: A Survey](IntrusiondetectionandBigHeterogeneousDataaSurvey.md) | Background on intrusion detection, heterogeneous security data, and processing challenges. |
| Gustavo de Carvalho Bertoli et al. | [An End-to-End Approach to Machine Learning in IDS: A Case Study of Stateless TCP Scan Detection](abordagem-fim-a-fim-para-uso-de-aprendizado-de-maquina.md) | End-to-end deployment and evaluation of an ML-based intrusion detector. |
| Iman Sharafaldin, Arash Habibi Lashkari, and Ali A. Ghorbani | [Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization](toward-generating-intrusion-model.md) | Construction of CIC-IDS2017, traffic scenarios, flow features, and labeling. |
| Scott M. Lundberg et al. (2020) | [From Local Explanations to Global Understanding with Explainable AI for Trees](from-local-explanations-to-global-understanding-with-explainable-ai-for-trees.md) | Foundations of explanations for tree ensembles and TreeSHAP, the path-dependent and interventional feature perturbations, and their complexity. |
| Scott M. Lundberg et al. (2019) | [Explainable AI for Trees: From Local Explanations to Global Understanding](from-local-to-global-understanding.md) | Preprint version of the 2020 article, with the Tree SHAP and Independent Tree SHAP algorithms and the supplementary figures. |

The Bertoli et al. title is rendered in English for this index. The linked transcription retains the original Portuguese title and text.

The Lundberg et al. (2020) transcription is the author manuscript NIHMS1601475 from [PubMed Central (PMC7326367)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7326367/). The final edited form was published in Nature Machine Intelligence 2(1):56–67, [doi:10.1038/s42256-019-0138-9](https://doi.org/10.1038/s42256-019-0138-9). The 2019 document is the arXiv preprint 1905.04610, whose title and section structure differ from the published article.

Original PDFs may be available locally but are excluded from version control by the repository's [ignore rules](../../.gitignore).

## Additional references

These references link to their external documents or publication pages. Local transcriptions are not currently included.

| Authors and year | Article document | Relevance to the project |
|---|---|---|
| Engelen, Rimmer, and Joosen (2021) | [Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study](https://doi.org/10.1109/SPW53761.2021.00009) | Problems in traffic generation, flow construction, feature extraction, and labeling that inform dataset inspection and limitations. |
| Liu, Engelen, Lynar, Essam, and Joosen (2022) | [Error Prevalence in NIDS datasets: A Case Study on CIC-IDS-2017 and CSE-CIC-IDS-2018](https://ieeexplore.ieee.org/abstract/document/9947235). IEEE CNS 2022. | Publication of the Improved CIC-IDS2017 used in this project. |
| Authors not stated (no date) | Documentation website "Error Prevalence in NIDS datasets": [Datasets Download](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html) and [CIC-IDS 2017](https://intrusion-detection.distrinet-research.be/CNS2022/CICIDS2017.html) pages | Definition of the Attempted label, the recommendation to relabel Attempted flows as Benign, the Attempted categories, and the reason for keeping the DoS Hulk label. Accompanies Liu et al. (2022). |
| Kalibera and Jones (2013) | [Rigorous Benchmarking in Reasonable Time](https://kar.kent.ac.uk/33611/) | Repetitions, performance variability, and confidence intervals for benchmarking. |
| Nugraha, Jnanashree, and Bauschert (2025) | [A Versatile XAI-Based Framework for Efficient and Explainable Intrusion Detection Systems](https://link.springer.com/article/10.1007/s12243-025-01118-9) | An IDS framework using XGBoost, SHAP, and LIME that evaluates explanation generation time. |
| Dash and Acken (2026) | [Intrusion Detection Latency: The Neglected Metric](https://link.springer.com/article/10.1186/s42400-026-00574-7) | Definitions and decomposition of IDS latency to inform measurement points. |
| Ogunseyi et al. (2026) | [Performance Analysis of Explainable Deep Learning-Based Intrusion Detection Systems for IoT Networks: A Systematic Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12845731/) | Detection performance, computational cost, and explanation quality, with a focus on deep learning and IoT. |
| Tran Duc Le, Truong Duy Dinh, Phuc Hao Do, and Van Dai Pham (2026) | [Explanation-Surface Governance in XAI-Enabled Network Intrusion Detection under Resource Constraints](https://doi.org/10.21203/rs.3.rs-9800570/v1). Research Square preprint, v1. | XAI-Gate compares explanation-service policies under finite capacity, including threshold selection and FIFO queues. |
| Abdurrahman Tolay (2026) | [Beyond Detection Accuracy: Measuring Explanation Cost, Stability, and Utility for Resource-Aware IoT Intrusion Detection](https://arxiv.org/abs/2608.10349). arXiv preprint, 2608.10349v1. | TreeSHAP timing for Random Forest and XGBoost, selective explanation, and cost–coverage trade-offs on CICIoT2023. |
| Shapley (1953) | [A Value for n-Person Games](https://doi.org/10.1515/9781400881970-018). In Contributions to the Theory of Games, vol. 2. | Origin of the Shapley value in cooperative game theory, on which SHAP and TreeSHAP are based. |
| Lundberg and Lee (2017) | [A Unified Approach to Interpreting Model Predictions](https://proceedings.neurips.cc/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html). NIPS 2017. | SHAP values as the only additive feature attributions that satisfy local accuracy, missingness, and consistency. |
| Adadi and Berrada (2018) | [Peeking Inside the Black-Box: A Survey on Explainable Artificial Intelligence (XAI)](https://doi.org/10.1109/ACCESS.2018.2870052). IEEE Access 6. | Survey of explainable artificial intelligence that supports the article's definition of XAI. |
| Breiman (2001) | [Random Forests](https://doi.org/10.1023/A:1010933404324). Machine Learning 45(1). | Original description of the Random Forest classifier used in this project. |
| Chen and Guestrin (2016) | [XGBoost: A Scalable Tree Boosting System](https://doi.org/10.1145/2939672.2939785). KDD 2016. | Original description of the XGBoost classifier used in this project. |
| Shwartz-Ziv and Armon (2022) | [Tabular data: Deep learning is not all you need](https://doi.org/10.1016/j.inffus.2021.11.011). Information Fusion 81. | Comparison in which XGBoost outperforms recent deep models proposed for tabular data and requires less tuning. |
| Grinsztajn, Oyallon, and Varoquaux (2022) | [Why Do Tree-Based Models Still Outperform Deep Learning on Typical Tabular Data?](https://proceedings.neurips.cc/paper_files/paper/2022/hash/0378c7692da36807bdec87ab043cdadc-Abstract-Datasets_and_Benchmarks.html). NeurIPS 2022, Datasets and Benchmarks Track. | Benchmark on 45 tabular datasets in which tree-based models remain state of the art on medium-sized data, about 10,000 samples. |
| Hendrickx, Perini, Van der Plas, Meert, and Davis (2024) | [Machine learning with a reject option: a survey](https://doi.org/10.1007/s10994-024-06534-x). Machine Learning 113(5). | Classification with a reject option, which abstains from predictions likely to be wrong and can defer them to a human expert. It supports the uncertainty criterion of the conditional synchronous strategy. |
| Lantz, Heller, and McKeown (2010) | [A Network in a Laptop: Rapid Prototyping for Software-Defined Networks](https://doi.org/10.1145/1868447.1868466). HotNets 2010. | Mininet, the network emulator that connects the traffic replay host to the NIDS host. |

## Software documentation

| Project | Documentation | Relevance to the project |
|---|---|---|
| XGBoost | [Introduction to Boosted Trees](https://xgboost.readthedocs.io/en/stable/tutorials/model.html), [Parameters](https://xgboost.readthedocs.io/en/stable/parameter.html), and [Installation Guide](https://xgboost.readthedocs.io/en/stable/install.html) | Additive prediction with boosted trees, binary logistic objective, histogram-based training on CPU, and the CPU-only Python package. |
| shap 0.54.1 | [GitHub repository](https://github.com/shap/shap) | TreeSHAP implementation used by the NIDS. With `feature_perturbation="tree_path_dependent"`, it explains only the raw output of the trees. |
| CICFlowMeter, fork by Gints Engelen, commit 13a061520b | [GitHub repository](https://github.com/GintsEngelen/CICFlowMeter) | Flow extractor corrected by the authors of the Improved CIC-IDS2017 and used by the NIDS, including its rules for terminating a flow. |
| CNS2022_Code, by Gints Engelen | [GitHub repository](https://github.com/GintsEngelen/CNS2022_Code) | Code of the Improved CIC-IDS2017. It describes the PCAP preparation with `pcapfix` and `reordercap`, and its labelling notebook stores the two header-length attributes as 16-bit integers. |
| Tcpreplay 4.6.2, by AppNeta | [GitHub repository](https://github.com/appneta/tcpreplay) | `tcpreplay-edit` replays the traffic segment at the original capture speed and rewrites the addresses of each copy. |
| Linux kernel documentation, 7.4.0-rc3 | [Segmentation Offloads](https://docs.kernel.org/networking/segmentation-offloads.html) | Generic receive offload assembles received frames into larger ones, which is why the offloads of the virtual interfaces are disabled before capture. |

## Maintaining the index

Add a corresponding entry when a new article document is added. Keep local links relative to this directory and retain extracted figures with their transcription. For references hosted elsewhere, link directly to the document, DOI, or publication page.

[Project README](../../README.md) · [Repository instructions](../../AGENTS.md)
