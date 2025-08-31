import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pathlib import Path
import subprocess
import re
from datetime import datetime
from jinja2 import Template, StrictUndefined

from hpc_performance_testing.utils import load_template, validate_path
from hpc_performance_testing.config import write_test_instance_meta, load_config, TestItem, FullConfig
from hpc_performance_testing.logger import LoggerManager, run_and_log_subprocess
from hpc_performance_testing.strategy import ScalingStrategy
from hpc_performance_testing.output import Job_FIELD, JobDataFrame
from hpc_performance_testing.types import MemSize
# get logger
logger = LoggerManager.get_logger()

@dataclass
class TestInstance:
    """Shared data structure for test instance information"""
    path: Path
    result_dir_base: Path
    repo_dir: Path
    config: FullConfig

class CodeBuilder:
    BUILD_TEMPLATE = load_template("build_all.sh.j2")

    def __init__(self, test_instance: TestInstance):
        self.test_instance = test_instance
        self._add_gpu_build_dflag()

    def _add_gpu_build_dflag(self):
        gpu_build = self.test_instance.config.hpc.gpu_build

        if gpu_build == "cuda":
            self.gpu_dflag = "-DAMReX_GPU_BACKEND=CUDA"

        elif gpu_build == "hip":
            self.gpu_dflag = "-DAMReX_GPU_BACKEND=HIP"

        else:
            raise NotImplementedError(
                f"Unsupported GPU backend: '{gpu_build}'. "
                "Supported options are: 'cuda' and 'hip'."
            )

    
    def generate_and_run_build(self) -> None:
        with open(self.BUILD_TEMPLATE) as f:
            build_temp = Template(f.read())

        re_build = build_temp.render(
        shell = self.test_instance.config.hpc.shell,
        test_instance = str(self.test_instance.path),
        env_setup_script = self.test_instance.config.paths.environment,
        tests = self.test_instance.config.tests,
        gpu_build_flag = self.gpu_dflag
        )
        build_file = self.test_instance.path/"build_all.sh"
        with open(build_file, "w") as f:
            f.write(re_build)
        logger.info("✅ Build script generated: build_all.sh")
        # Run the build script
        run_and_log_subprocess([self.test_instance.config.hpc.shell, build_file], logger=logger, batch_size=1)
        logger.info("Finish building the tests.")


class JobScheduler(ABC):
    """Abstract base class for different HPC job schedulers"""
    
    def __init__(self, test_instance: TestInstance, template_file: str):
        self.test_instance = test_instance
        self.template = self._load_template(template_file)
        
    @abstractmethod
    def get_job_id(self, submit_stdout: str) -> str:
        """Extract job ID from submission output"""
        pass
    
    @abstractmethod
    def submit_job(self, jobfile: str) -> str:
        """Submit job and return job ID"""
        pass
    
    def _set_extra_var(self, **job_params) -> dict|None:
        """Set extra variables needed to render template;
           Overwrite this function if needed
        """
        return None

    def _load_template(self, template_file: str) -> Template:
        """Load and return the job template for this scheduler"""
        with open(load_template(template_file)) as f:
            return Template(f.read(), undefined=StrictUndefined)
    
    def _estimate_nnodes(self, core_per_node, ncores):
        """Estimate number of nodes needed"""
        return (int(ncores) + int(core_per_node) - 1) // int(core_per_node)
    
    def _read_ncell(self, input_file) -> list:
        with open(input_file) as f:
            content = f.read()
            pattern = r'amr\.n_cell\s*=\s*((?:\d+\s*)+)'
            match = re.search(pattern, content)
            if not match:
                raise ValueError("amr.n_cell not found or invalid format in input file")
            
            # Split the matched group into integers
            nums = [int(x) for x in match.group(1).strip().split()]

        return nums
    
    def _get_scaling_strategy(self):
        scaling = self.test_instance.config.scaling.strategy
        max_cores = self.test_instance.config.scaling.max_cores
        min_cores = self.test_instance.config.scaling.min_cores
        
        strategies = {
        "weak_3d": ScalingStrategy.weak_3d_scaling
        }

        if scaling not in strategies:
            raise ValueError(f"Unsupported scaling strategy: {scaling}")
        
        return strategies[scaling], min_cores, max_cores
    
    def _get_job_settings(self, test_item: TestItem):
        
        # get global job settings
        job_settings = self.test_instance.config.global_job_settings.model_dump()

        if test_item.job_settings:
             test_job_setting = {k: v for k, v in test_item.job_settings.model_dump().items() if v is not None}
             job_settings.update(test_job_setting)

        return job_settings 
    
    def _prepare_template_vars(self, test_item: TestItem, **job_settings) -> dict:
        """Prepare common template variables used by all schedulers"""
        
        # get shell and environment
        # todo: restructure config.yaml for better grouping
        env_var = {
            "shell": self.test_instance.config.hpc.shell,
            "environment": self.test_instance.config.paths.environment,
        }


        # test specific vars
        test_var = {
            "name": test_item.name,
            "target": str(self.test_instance.repo_dir/f"build_{test_item.name}/src/problems"/test_item.target),
        
        }
        
        # get ncell args
        ncell_params = job_settings.get("ncell_params")
        _core = job_settings.get("core")
        ncell_args = "" if _core == 1 else ncell_params[1]

        # notice test specific settings will overwrite global settings
        base_var = {**env_var, **test_var, **job_settings, "ncell_args": ncell_args}
        
        # extra vars
        extra_var = self._set_extra_var(**base_var)
       
        return {**base_var, **extra_var} if extra_var else base_var
        
    def _create_symlink_file(self, target_file_path: Path, link_path: Path):
        test_input_base = Path(self.test_instance.config.paths.test_inputs).resolve()
        target_file_subpath = target_file_path.relative_to(test_input_base)
        link_file_path = link_path/target_file_subpath
        link_file_path.parent.mkdir(parents=True, exist_ok=True)
        if not link_file_path.exists():
            link_file_path.symlink_to(target_file_path)

    def _validate_link_file(self, link_files, run_path):
        #todo: prevent duplicated link_files 
        if link_files:
            for lf in link_files:
                # validate for absolute path
                if Path(lf).is_absolute():
                    validate_path(lf)
                    continue
                
                test_inputs_base = Path(self.test_instance.config.paths.test_inputs).resolve()
                run_path = Path(run_path)
                
                _candidate_in_test_inputs = (test_inputs_base/lf).resolve(strict=False)
                if _candidate_in_test_inputs.is_relative_to(test_inputs_base):
                    validate_path(_candidate_in_test_inputs)
                    self._create_symlink_file(_candidate_in_test_inputs, run_path)
                    continue
                
                validate_path(run_path/lf)

                
        
    def render_single_job_script(self, test_item: TestItem, **job_settings) -> str:
                
        # Get template variable value
        template_vars = self._prepare_template_vars(test_item, **job_settings)
        
        return self.template.render(**template_vars)
    
    def generate_all_job_scripts(self):
        """Generate all job scripts for all tests - shared logic across schedulers"""
        
        # get scaling strategy
        scaling_func, min_cores, max_cores = self._get_scaling_strategy()

        # Initiate dataframe
        output = JobDataFrame(Job_FIELD)
        # breakpoint()
        for test in self.test_instance.config.tests:
            input_file = str(self.test_instance.config.paths.test_inputs / test.input_file)
            init_ncell = self._read_ncell(input_file)
            core_dict = scaling_func(init_ncell, min_cores, max_cores)
            
            for core, arg_value in core_dict.items():
                job_settings = self._get_job_settings(test)
                # calculate the number of nodes needed
                core_per_node = job_settings["ntasks_per_node"]
                # sanity check
                assert core_per_node is not None
                node = self._estimate_nnodes(core_per_node, core)

                # create a directory for each test job
                test_folder = f"{test.name}_n{core}"
                result_dir = self.test_instance.result_dir_base / test_folder
                os.makedirs(result_dir, exist_ok=True)
                
                if test.link_file:
                    self._validate_link_file(test.link_file, result_dir)

                # Prepare job parameters
                _job_params = {
                    'core': core,
                    'node': node,
                    'input_file': input_file,
                    'ncell_params': arg_value,                    
                    'result_dir': str(result_dir),
                }

                job_settings.update(_job_params)

                # overwrite ntasks-per-node if core < ntasks-per-node in config.yaml
                if core < job_settings["ntasks_per_node"]:
                    job_settings["ntasks_per_node"] = core
                
                # Generate job script using scheduler-specific logic
                rendered = self.render_single_job_script(test, **job_settings)
                
                job_name = result_dir/f"{test.name}_n{core}.sh"
                with open(job_name, "w") as f:
                    f.write(rendered)
                logger.info(f"✅ Job script generated: {job_name}")

                # Submit job using scheduler-specific method
                job_id = self.submit_job(job_name)
                # job_id = 1
                # Record job information
                output_params = {
                    "job_id": job_id,
                    "test_name": test.name,
                    "test_folder": test_folder,
                    "n_cell": arg_value[0],
                    "n_gpu": core,
                    "gpus_per_node": job_settings["ntasks_per_node"],
                    "n_nodes": node,
                }

                # sanity check
                assert set(output_params.keys()) == set(Job_FIELD), \
                f"Mismatched keys:\nMissing: {set(Job_FIELD) - set(output_params)}\n" \
                f"Extra: {set(output_params) - set(Job_FIELD)}"

                output.add_job_entry(**output_params)
        
        # save dataframe
        output.save(self.test_instance.result_dir_base/"job_submission.parquet")
    
    
class SlurmScheduler(JobScheduler):
    """job scheduler implementation on SLURM HPCs"""
    def get_job_id(self, submit_stdout: str) -> str:
        match = re.search(r"Submitted batch job (\d+)", submit_stdout)
        return match.group(1) if match else None 
    
    def submit_job(self, jobfile: str) -> str:
        try:
            submit = subprocess.run(["sbatch", jobfile], capture_output=True, text=True, check=True)
            job_id = self.get_job_id(submit.stdout)
            logger.info(f"Submit job: {job_id}")
        except subprocess.CalledProcessError as e:
            msg = (
            f"Job submission failed!\n"
            f"Command: {' '.join(e.cmd)}\n"
            f"Return code: {e.returncode}\n"
            f"stderr:\n{e.stderr.strip()}"
            )
            logger.error(msg)
            sys.exit(1)
        return job_id
    

class PbsScheduler(JobScheduler):
    """job scheduler implementation on PBS HPCs"""
    def _set_extra_var(self, **params):
        if self.test_instance.config.hpc.cluster == "gadi":
            required_keys = ["cpus_per_task", "core", "mem_per_node", "jobfs_per_node", "node"]
            missing_keys = [key for key in required_keys if key not in params or params[key] is None]

            if missing_keys:
                raise ValueError(f"Missing or None parameters for Gadi jobs: {missing_keys}")

            return self._gadi_var(
                cpus_per_task=params["cpus_per_task"],
                core=params["core"],
                mem_per_node=params["mem_per_node"],
                jobfs_per_node=params["jobfs_per_node"],
                node=params["node"]
            )
            
        else:
            return super()._set_extra_var(**params)

    def _gadi_var(self, cpus_per_task: int, core: int, 
                  mem_per_node: MemSize, jobfs_per_node: MemSize, node: int):
        
        return {
            "ncpus": cpus_per_task * core,
            "mem": mem_per_node.scale(node),
            "jobfs": jobfs_per_node.scale(node),
        }
        

    def get_job_id(self, submit_stdout: str) -> str:
        match = re.search(r"^(\d+)", submit_stdout.strip())
        return match.group(1) if match else None

    def submit_job(self, jobfile: str) -> str:
        try:
            submit = subprocess.run(["qsub", jobfile], capture_output=True, text=True, check=True)
            job_id = self.get_job_id(submit.stdout)
            logger.info(f"Submit job: {job_id}")
        except subprocess.CalledProcessError as e:
            msg = (
            f"Job submission failed!\n"
            f"Command: {' '.join(e.cmd)}\n"
            f"Return code: {e.returncode}\n"
            f"stderr:\n{e.stderr.strip()}"
            )
            logger.error(msg)
            sys.exit(1)
        return job_id
        

class JobCreator:
    """Main orchestrator class that uses composition"""
    
    def __init__(self, config: dict):
        self.config = config
        self._prepare()
        self.code_builder = CodeBuilder(self.test_instance)
        self.scheduler = self._create_scheduler()
    
    def _set_timestamp(self):
        return datetime.today().strftime("%Y%m%d%H%M%S")
    
    def _make_dir(self, dir_path: Path, parents=True, exist_ok=True):
        try:
            dir_path.mkdir(parents=parents, exist_ok=exist_ok)
        except Exception as e:
            
            logger.error(f"Failed to create directory {dir_path}: {e}")
            sys.exit(1)
        return dir_path
    
    def _create_test_instance(self) -> TestInstance:
        """Create test instance with all necessary paths and metadata"""
        timestamp = self._set_timestamp()
        working_dir = self.config.paths.working_dir / "performance_test"
        test_instance_path = self._make_dir(working_dir / timestamp, parents=True, exist_ok=False)
        logger.info(f"Initialize test instance: {test_instance_path}")
        result_dir_base = self._make_dir(test_instance_path / "results", parents=True, exist_ok=False)
        logger.info(f"Create results directory: {result_dir_base}")
        repo_dir = test_instance_path / "quokka"
        
        self.test_instance = TestInstance(
            path=test_instance_path,
            result_dir_base=result_dir_base,
            repo_dir=repo_dir,
            config=self.config,
        )
    
    def _prepare(self):
        # create test instance
        self._create_test_instance()

        # write test instance meta yaml file
        write_test_instance_meta(self.config, self.test_instance.path)

        # add pipeline log handler
        LoggerManager.add_pipeline_log(self.test_instance.path)

    def _create_scheduler(self) -> JobScheduler:
        """Factory method to create appropriate scheduler based on config"""
        # Read HPC type from config, with default fallback
        hpc = self.config.hpc.cluster
        
        schedulers = {
            "nt": [SlurmScheduler, "job_nt.sh.j2"],
            "setonix": [SlurmScheduler, "job_setonix.sh.j2"],
            "frontier": [SlurmScheduler, "job_frontier.sh.j2"],
            "gadi": [PbsScheduler, "job_gadi.sh.j2"],
            # Add more schedulers as needed
        }
        
        if hpc not in schedulers.keys():
            raise ValueError(f"Unsupported HPC: {hpc}")
        scheduler, temp_file = schedulers[hpc]
        return scheduler(self.test_instance, temp_file)   
    
    def build_tests(self) -> None:
        """Build all tests"""
        self.code_builder.generate_and_run_build()
    
    def generate_and_submit_jobs(self) -> None:
        """Generate job scripts and submit them"""
        self.scheduler.generate_all_job_scripts()
           
    def run_full_pipeline(self) -> None:
        """Run the complete pipeline: build tests and submit jobs"""
        self.build_tests()
        self.generate_and_submit_jobs()

if __name__ == "__main__":
    config = load_config("config.yaml")
    # breakpoint()
    job_creator = JobCreator(config)
    job_creator.run_full_pipeline()
    