#!/bin/bash
#SBATCH --job-name=iris_qwen32b
#SBATCH --gpus-per-node=nvidia_h100_80gb_hbm3_3g.40gb:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=100G
#SBATCH --time=08:00:00
#SBATCH --output=iris_seq_%j.out

# Usage:
#   sbatch run_iris.sbatch jenkinsci__perfecto-plugin_CVE-2020-2261_1.17 cwe-078wLLM

PROJECT_SLUG="${1:?Provide project slug (e.g. jenkinsci__perfecto-plugin_CVE-2020-2261_1.17)}"
QUERY_NAME="${2:?Provide query name (e.g. cwe-078wLLM)}"

module load StdEnv/2023
module load cuda/12.2
module load apptainer

cd ~/AutoSec/AutoSec/Experiments/Finder/

# Conda setup command (activate the env inside container)
CONDA_SETUP="source /opt/conda/etc/profile.d/conda.sh && conda activate iris"

nvidia-smi

export HF_HOME=/scratch/vvv/huggingface
export TRANSFORMERS_CACHE=/scratch/vvv/huggingface
export HF_DATASETS_CACHE=/scratch/vvv/huggingface/datasets


# Step 1 - fetch project
srun apptainer exec --nv --bind /etc/pki/tls/certs:/etc/pki/tls/certs --bind /etc/pki/ca-trust/extracted/pem iris.sif bash -c "
    cd ~/AutoSec/AutoSec/Experiments/Finder/ &&
    $CONDA_SETUP &&
    python -c 'import torch; print(torch.cuda.is_available(), torch.version.cuda, torch.cuda.get_device_name(0))'
    python scripts/fetch_and_build.py --filter $PROJECT_SLUG
"

# Step 2 - build codeql db
srun apptainer exec --nv --bind /etc/pki/tls/certs:/etc/pki/tls/certs --bind /etc/pki/ca-trust/extracted/pem iris.sif bash -c "
    cd ~/AutoSec/AutoSec/Experiments/Finder/ &&
    $CONDA_SETUP &&
    python scripts/build_codeql_dbs.py --project $PROJECT_SLUG
"

# Step 3 - run IRIS analysis
srun apptainer exec --nv --bind /etc/pki/tls/certs:/etc/pki/tls/certs --bind /etc/pki/ca-trust/extracted/pem iris.sif bash -c "
    cd ~/AutoSec/AutoSec/Experiments/Finder/ &&
    $CONDA_SETUP &&
    python src/iris.py --query $QUERY_NAME --run-id test --llm qwen2.5-32b $PROJECT_SLUG
"
