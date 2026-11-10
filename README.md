# NIDS XAI Benchmark

An undergraduate research project investigating how TreeSHAP explanations affect the latency and resource usage of a Network Intrusion Detection System (NIDS).

The study uses tree-based classifiers, Random Forest and XGBoost, and public network traffic data from the Improved CIC-IDS2017 dataset.

## Research scope

The planned experiments compare four strategies under controlled traffic loads.

| Strategy | Behavior |
|---|---|
| No XAI | Make the classification available without generating an explanation. |
| Fully synchronous XAI | Explain every flow before making its classification available. |
| Conditional synchronous XAI | Explain selected flows before making their classifications available. |
| Asynchronous XAI | Make the classification available and generate its explanation in a separate process. |

Measurements distinguish model inference time, classification delivery latency, and explanation delivery latency. The comparison also considers throughput, CPU and memory usage, explanation coverage, queue growth, and discarded requests.

The repository currently contains the research documents, bibliography, dataset inspection script, and inspection results. Model training, NIDS implementation, and the experimental campaign are planned in the roadmap.

## Project materials

| Material | Purpose |
|---|---|
| [Research proposal](overleaf/proposta.tex) | Research question, objectives, scope, and proposed methodology. |
| [Development roadmap](roadmap.md) | Development stages and completion criteria. |
| [GitHub Project](https://github.com/users/pedro-fs-garcia/projects/5/views/4) | Stage cards containing tasks, dependencies, and execution guidance. |
| [Bibliography](docs/bibliography/README.md) | Article index linking local transcriptions and external references. |
| [ABNT article template](overleaf/artigo.tex) | LaTeX starting point for the academic manuscript. |
| [Dataset inspection script](scripts/inspecionar_cicids2017.py) | Reproducible inspection of the five daily CSV files. |
| [Dataset inspection report](relatorios/inspecao-cicids2017.md) | Findings about classes, invalid values, duplicates, and input integrity. |
| [Detailed inspection results](relatorios/inspecao-cicids2017.json) | Counts, statistics, examples, and file hashes in JSON format. |
| [Agent instructions](AGENTS.md) | Repository working rules and bibliography guidance. |

## Dataset inspection

The local dataset directory is `cicids-dataset/`. It contains the five daily CSV files and `CICIDS2017_improved.zip`. Obtain the improved dataset through the [authors' dataset page](https://intrusion-detection.distrinet-research.be/CNS2022/Dataset_Download.html).

The inspection script requires Python 3 and GNU `sort`. It uses the Python standard library and reads the CSV files sequentially.

Run the following command from the repository root, using explicit paths for the current directory layout.

```bash
python3 scripts/inspecionar_cicids2017.py \
  --input cicids-dataset \
  --archive cicids-dataset/CICIDS2017_improved.zip \
  --output relatorios
```

This command regenerates the Markdown and JSON inspection reports in `relatorios/`. It checks input hashes before and after inspection and preserves the original dataset files. Data preparation and training will produce separate derived artifacts.

The existing inspection covers 2,099,976 records and 91 columns. Its findings include five records with infinite traffic rates, negative header-length values, and repeated traffic attribute vectors. The report documents these findings for subsequent treatment decisions.

The dataset directory and PDF files are excluded from version control by the current [ignore rules](.gitignore).

## Reading the bibliography

Start with the [bibliography index](docs/bibliography/README.md). Each local paper links to its Markdown transcription. Additional references link to their publisher, DOI, or institutional document page.

Original article wording and source languages are preserved in the transcriptions. Extracted figures are stored alongside them in `docs/bibliography/assets/`.
