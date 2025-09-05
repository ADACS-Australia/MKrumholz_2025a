# Quokka HPC Performance Testing Pipeline


This package provides a pipeline for performance benchmarking of the **[quokka](https://github.com/quokka-astro/quokka/tree/development)** code on HPC systems.  
It automates test building, job submission, monitoring, result extraction and cleanup across multiple clusters.


## 1. Installation on HPC (recommended)

**Prerequisites**
- `python >= 3.10`

**Note:** On most HPC systems, Python is provided as a module (e.g. `module load python/3.11.3`). We recommend using the site-provided module. 

**Steps**
1. Clone the repository and enter the project directory:
   ```bash
   git clone git@github.com:ADACS-Australia/MKrumholz_2025a.git
   cd MKrumholz_2025a
   ```

2. Load a Python module on the HPC (example):
   ```bash
   module load python/3.11.3
   ```

3. Create and activate a virtual environment:
   ```bash
   python -m venv /path/to/my_venv
   source /path/to/my_venv/bin/activate
   ```
4. Install the package inside the environment:
    ```bash
    python -m pip install .
    ```

## 2. Core Design Overview
The pipeline is configuration-driven and tailored for running quokka benchmarks:

* A YAML file specifies the required job resources,scaling strategy and tests to run (job settings + test items).
  
* The pipeline uses Jinja2 templates to:
  - Clone quokka and build the tests automatically.  
  - Generate job scripts for specific HPC systems.  
    - Currently supported clusters: NT (Ngarrgu Tindebeek), Setonix, Gadi, Frontier.  

* An environment script prepares the runtime environment on HPC (modules, environment variables, Python venv activation).

To run the pipeline you need to prepare the following for each HPC system:

1. An environment script.

2. A YAML configuration file (commonly named config.yaml).

## 3. Preparing an Environment Script

Before submitting jobs, you must prepare a script that:

* Loads the required modules for quokka on your HPC.

* Exports required environment variables.

* Activates your Python virtual environment created in step 3 of [Installation](#1-installation-on-hpc-recommended)

Examples for NT, Setonix, Gadi, and Frontier are provided in the [hpc_env](https://github.com/ADACS-Australia/MKrumholz_2025a/tree/main/hpc_env) folder.

**!!Important:** Update the path to your Python venv in the script.

## 4. Preparing a YAML configuration File

The configuration file defines how the pipeline builds and runs quokka tests.  
It is divided into sections: `hpc`, `paths`, `global_job_settings`, `scaling`, and `tests`.  

Examples are provided in the [config_yaml](https://github.com/ADACS-Australia/MKrumholz_2025a/tree/main/config_yaml) folder.  

---

#### `hpc` section

| Field       | Required | Type   | Allowed values                      | Default     | Description                                               |
| ----------- | -------- | ------ | ----------------------------------- | ----------- | --------------------------------------------------------- |
| `cluster`   | yes      | str | any | –           | Target HPC system. Determines which job template is used. No hard restriction is applied, but the pipeline currently only supports `nt`, `setonix`, `gadi`, `frontier`. |
| `scheduler` | yes      | str | `slurm`, `pbs`                      | –           | Scheduler type on the cluster.                            |
| `gpu_build` | yes      | str | `cuda`, `hip`                       | –           | GPU backend for Quokka build.                             |
| `shell`     | yes       | str  | any valid shell path                | –   | Shell used in job scripts.                                |

---

#### `paths` section

| Field         | Required | Type | Default | Description                                                                                                   |
| ------------- | -------- | ---- | ------- | ------------------------------------------------------------------------------------------------------------- |
| `working_dir` | no       | path | "./"    | Root directory where test runs will be saved  |                                                                      
| `environment` | yes      | path | –       | Path to environment setup script (see [Preparing an Environment Script](#3-preparing-an-environment-script)). |
| `test_inputs` | yes      | str | –       | Root directory of test input file `.in` files. |
| `link_files_root` | yes      | str | –       | Root directory of test link files files. |                                                        

**Note:** `working_dir` and `environment` are validated when the YAML file is loaded (they must exist before starting the test run).  
In contrast, `test_inputs` and `link_files_root` are validated at runtime, after the tests have been built. You may use the environment variable `$QUOKKA` in these two fields, which points to the Quokka repository cloned at runtime.

---
#### `global_job_settings` section

Global job defaults applied to all tests (can be overridden per test via `job_settings`).

| Field             | Required | Type | Default         | Description                                  |
| ----------------- | -------- | ---- | --------------- | -------------------------------------------- |
| `ntasks_per_node` | no       | int  | cluster default | Max number of tasks (MPI ranks) to run per node. |
| `cpus_per_task`   | no       | int  |  –              | Number of CPUs allocated to each task.       |
| `walltime`        | no       | str  | cluster default | Job walltime in `hh:mm:ss`.                  |
| `mem_per_cpu`     | no       | str  | cluster default | Memory per CPU (e.g. `4G`, `500M`).          |
| `mem_per_node`    | no       | str  | cluster default | Memory per node (e.g. `64G`).                |
| `jobfs_per_node`  | no       | str  | cluster default | Job filesystem scratch space per node. **Need in Gadi jobs only**.     |
| `partition`       | no       | str  | cluster default | Partition/queue to submit jobs into.         |
| `account`         | no       | str  | user default    | Project or account to charge compute time.   |
| `mpi_opt`         | no       | str  | –               | Extra MPI options passed to `srun`/`mpirun`. **Note:** `-np` is not supported; the number of processes is determined by job directives. |


---

#### `scaling` section


| Field       | Required | Type | Allowed values   | Default | Description                                                                              |
| ----------- | -------- | ---- | ---------------- | ------- | ---------------------------------------------------------------------------------------- |
| `strategy`  | yes      | str  | `weak_3d`        | –       | Scaling strategy. Currently only `weak_3d` is supported (may be extended in the future). |
| `min_cores` | no       | int  | any positive int | 1       | Minimum number of cores to include in tests.                                             |
| `max_cores` | yes      | int  | positive int larger or equal to `min_cores` | –       | Maximum number of cores to scale to.                                                     |

---

### `tests` section

Each entry in `tests` defines a single quokka test case.

| Field          | Required | Type      | Default | Description                                |
| -------------- | -------- | --------- | ------- | ------------------------------------------ |
| `name`         | yes      | str    | –       | Friendly name for the test.                |
| `target`       | yes      | str      | –       | Path to Quokka target (relative to `<build dir>/src/problems`). |
| `input_file`   | yes      | str | –       | Input `.in` file to run.                   |
| `link_file`   | no      | str or list  | None      | Link file(s) required by `input_file`                 |
| `cmake_cache`  | no       | list[str] | None     | Extra CMake options for Quokka build.      |
| `job_settings` | no       | same as `global_job_settings`      | None      | Per-test job overrides.                    |

**Note:**  
The `job_settings` block accepts the same fields as [`global_job_settings`](#global_job_settings-section).  
Any value defined here overrides the corresponding global value.  
If a field is omitted, the global setting applies.

If `link_file` is not None, a symlink will be created at the relevant test directory. 

## 5. Running the Pipeline

The pipeline can be run either through the **CLI tool** (`hptest`) or directly from **Python functions**.  
Both interfaces provide the same functionality.

---
### 5.1 Submit jobs

**CLI**
```bash
hptest submit config.yaml
```
**Python**
```python
from hpc_performance_testing import submit_jobs
submit_jobs("config.yaml")
```

**Workflow**

1. Initialize

    * Create `runtime_err.log` in the current directory.

    * Validate the configuration file.

2. Create a test instance

    * Make folder: working_dir/performance_test/<timestamp>/.

    * Write `test_instance.yaml` in the current directory with:

        * All configuration fields

        * A runtime section containing the timestamp and path to the test instance folder

3. Build quokka

    * Render `build_all.sh` inside the test instance folder.

    * Build quokka into the quokka/ subfolder.

4. Create results structure

    * Start `perf_test.log` inside the test instance folder (info-level log).

    * Create a `results/` directory containing:
  
        * One subfolder per test (named by the test and its resources).

5. Render job scripts and submit
    * Job script is generated per test
    * When all jobs are submitted, create `job_submission.parquet` – records all submitted jobs and their resource requirements


```
performance_test/<timestamp>/
├── build_all.sh
├── perf_test.log
├── quokka/
└── results/
    ├── job_submission.parquet
    ├── test_hydro3d_blast_n1/
    │   └── test_hydro3d_blast_n1.sh
    └── test_hydro3d_blast_n8/
        └── test_hydro3d_blast_n8.sh

```

### 5.2 Check job status

**CLI**
```bash
hptest check test_instance.yaml
```

**Python**
```
from hpc_performance_testing import check_jobs
status = check_jobs("test_instance.yaml")
```

**Workflow**
1. Read `test_instance.yaml` to access test instance path
2. Read job IDs from `job_submission.parquet`
3. Query the scheduler (Slurm/PBS) for job status 
4. Create or update `results/job_exit_status.parquet` when detecting newly finished jobs, recording their final status and exit codes

**Return value**

* CLI prints: WAITING or FINISHED

* Python status: JobJobStatus.WAITING or JobJobStatus.FINISHED

### 5.3 Extract results

**CLI**
```bash
hptest extract test_instance.yaml
```

**Python**
```python
from hpc_performance_testing import extract_results
extract_results('test_instance.yaml')
```

**Workflow**
1. Reads `test_instance.yaml` to access test instance path.

2. Parse job output to get required metrics.

3. Writes metrics into `job_output.parquet` under `tests/`.

**Example of extracted results**
|     | job_id  | n_mpi_processes | zone_update_microseconds_per_update | zone_update_megaupdates_per_second | elapse_time | boundary_condition_inc_main_Name        | boundary_condition_inc_main_NCalls | boundary_condition_inc_main_Incl. Min | boundary_condition_inc_main_Incl. Avg | boundary_condition_inc_main_Incl. Max | boundary_condition_inc_main_Max % |
| --- | ------- | --------------- | ----------------------------------- | ---------------------------------- | ----------- | --------------------------------------- | ---------------------------------- | ------------------------------------- | ------------------------------------- | ------------------------------------- | --------------------------------- |
| 0   | 2165882 | 4               | 0.07963453312                       | 12.55736627                        | 3.271629046 | AMRSimulation::fillBoundaryConditions() | 1891                               | 0.4991                                | 0.6214                                | 0.7381                                | 22.56%                            |
| 1   | 2165884 | 8               | 0.0237902364                        | 42.03405058                        | 26.05459954 | AMRSimulation::fillBoundaryConditions() | 7978                               | 4.734                                 | 7.034                                 | 8.792                                 | 33.74%                            |

### 5.4 Cleanup

**CLI**
```bash
hptest cleanup <scenario>
```

**Python**
```python
from hpc_performance_testing import cleanup
cleanup(scenario="resubmit") # allowed scenario: resubmit, finished, delete_all
```

The pipeline relies on a single `test_instance.yaml` in the current directory to locate the active test instance.  
To avoid conflicts, starting a new test instance is blocked if a `test_instance.yaml` already exists.  

To start a new test run, cleanup is required. Three scenarios are supported:  

1. **resubmit**:
    
    Used when the previous submission failed, or when you simply want to start a fresh run.  
   * Move `test_instance.yaml` into the relevant test instance folder if available, otherwise delete it.  
   * Apply the same action to `runtime_err.log`. 

2. **finished**:
    
    Used when the test run has completed and you want to consolidate results.  
   * Move `test_instance.yaml` and `runtime_err.log` into the relevant test instance folder (delete them if this fails).  
   * Merge the Parquet files generated in previous steps (`job_submission.parquet`, `job_exit_status.parquet`, and `job_output.parquet`) into a single `job_summary.parquet`.  
   * Remove the original Parquet files after merging.  


3. **delete_all**:

    Used to completely remove a test run.  
   * Delete `test_instance.yaml`, `runtime_err.log`, and the entire test instance folder (including logs, results, build, and outputs).  
