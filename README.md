# HPC performance testing pipeline

### 1. Installation

Pre-requisite: `python >= 3.10`, `poetry > 2.0.0`(optional).

If using `poetry` for managing dependencies:
```
$ poetry install
```

otherwise:
```
$ pip install -e .
```

### 2. Preparation
Before running the code, we need to prepare the following files:

1. A bash script for managing environment
    - This script is used to manage loading modules, exporting environment variables and activating python environment.
2. test input files
3. A `config.yaml` file
    - update fields `script` and `test_inputs` accordingly

### 3. Use cases

#### 3.1 Submit jobs to HPC
```
from hpc_performance_testing import submit_jobs

submit_jobs("./config.yaml")
```
The function `submit_jobs` does the following:

1. create a directory in `working_dir` (specified in `config.yaml`)
2. clone the quokka repo
3. build the tests (build option and flags are specified in `config.yaml`)
4. create HPC jobs and submit them
5. create a parquet to store information related to job submission (e.g. job_id, cores, nodes)




