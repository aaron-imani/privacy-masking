# Privacy Masking for PDF Document Processing Using Large Language Models

## Goal
Identify and mask Personal Identifiable Information (PII) in PDF documents. We can assume the PDF is already converted to Markdown.

## Setup

1. Setup a Python virtual environment

```bash
pip install uv
uv venv --python 3.12 --seed 
source .venv/bin/activate
```

1. Install requirements

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Existing Approaches

According to Table 4 in [this paper](https://arxiv.org/pdf/2504.12308), [Microsoft Presidio](https://microsoft.github.io/presidio/) is the tool with the best performance for PII detection in text documents. However, the performance is not ideal as it misses some PII entities, e.g., 18.1% Credit card numbers, and it misclassifies the identified PIIs in several cases. You can see an example of Presidio's usecase by running the following script:

```bash
source .venv/bin/activate
python demo_presidio.py
```

## Potential Alternatives

### Fine-tuning Large Language Models

Google introduced a new family of open-source large language models, Gemma 3. In this family, there is a compact model called [Gemma3 270M](https://developers.googleblog.com/en/introducing-gemma-3-270m/) with only 270 million parameters, which is suitable for fine-tuning on specific tasks such as PII detection and masking. Several open-source PII datasets exist on HuggingFace that could be adopted to fine-tune the Gemma3 model. Following is a list of some of such datasets:

- [automated-analytics/gretel-pii-fine-grained](https://huggingface.co/datasets/automated-analytics/gretel-pii-fine-grained/)

- [automated-analytics/piiceetah-call-centre](https://huggingface.co/datasets/automated-analytics/piiceetah-call-centre)

- [automated-analytics/ai4privacy-pii-coarse-grained](https://huggingface.co/datasets/automated-analytics/ai4privacy-pii-coarse-grained)

- [ai4privacy/pii-masking-200k](https://huggingface.co/datasets/ai4privacy/pii-masking-200k)

- And many more datasets that can be found on HuggingFace

We have implemented a script to fine-tune the Gemma3 270M model on the [automated-analytics/gretel-pii-fine-grained](https://huggingface.co/datasets/automated-analytics/gretel-pii-fine-grained/) dataset. The script is available in the `finetune_gemma.py` file. To run the script, use the following command:

```bash
source .venv/bin/activate
python finetune_gemma.py
```

To use the fine-tuned model for PII detection and masking, you can run the following command:

```bash
source .venv/bin/activate
python demo_finetuned.py
```

You can see relevant literature for different prompting approaches for PII detection:

- [PII-Bench: Evaluating Query-Aware Privacy Protection Systems](https://openreview.net/pdf?id=uZ18l6OJzO)