# Privacy Masking for PDF Document Processing Using Large Language Models

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

1. Run [Microsoft Presidio](https://microsoft.github.io/presidio/installation/#__tabbed_1_2) Docker instances:

```bash
# Download Docker images
docker pull mcr.microsoft.com/presidio-analyzer
docker pull mcr.microsoft.com/presidio-anonymizer

# Run containers with default ports
docker run -d -p 5002:3000 mcr.microsoft.com/presidio-analyzer:latest
docker run -d -p 5001:3000 mcr.microsoft.com/presidio-anonymizer:latest
```