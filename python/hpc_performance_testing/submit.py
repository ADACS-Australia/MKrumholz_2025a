import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pathlib import Path
import subprocess
import re
from datetime import datetime
from jinja2 import Template

from hpc_performance_testing.utils import load_template
from hpc_performance_testing.config import write_test_instance_meta, load_config
from hpc_performance_testing.logger import LoggerManager, run_and_log_subprocess
from hpc_performance_testing.strategy import ScalingStrategy
from hpc_performance_testing.output import Job_FIELD, JobDataFrame

# get logger
logger = LoggerManager.get_logger()

@dataclass
class TestInstance:
    """Shared data structure for test instance information"""
    path: Path
    result_dir_base: Path
    repo_dir: Path
    config: dict

class CodeBuilder:
    BUILD_TEMPLATE = load_template("build_all.sh.j2")

    def __init__(self, test_instance: TestInstance):
        self.test_instance = test_instance
        self._add_gpu_build_dflag()

    def _add_gpu_build_dflag(self):
        self.gpu_dflag = ""
        if self.test_instance.config["hpc"]["gpu_build"] is None:
            pass
        elif self.test_instance.config["hpc"]["gpu_build"].upper() == "CUDA":
            self.gpu_dflag = "-DAMReX_GPU_BACKEND=CUDA"
            
        elif self.test_instance.config["hpc"]["gpu_build"].upper() == "HIP":
            self.gpu_dflag = "-DAMReX_GPU_BACKEND=HIP"
    
    def generate_and_run_build(self) -> None:
        with open(self.BUILD_TEMPLATE) as f:
            build_temp = Template(f.read())

        re_build = build_temp.render(
        shell = self.test_instance.config["hpc"]["shell"],
        test_instance = str(self.test_instance.path),
        env_setup_script = self.test_instance.config["hpc"]["env_setup_script"],
        tests = self.test_instance.config["tests"],
        gpu_build_flag = self.gpu_dflag
        )
        build_file = self.test_instance.path/"build_all.sh"
        with open(build_file, "w") as f:
            f.write(re_build)
        logger.info("✅ Build script generated: build_all.sh")
        # Run the build script
        # run_and_log_subprocess([self.test_instance.config["hpc"]["shell"], build_file], logger=logger, batch_size=1)
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

    def _load_template(self, template_file: str) -> Template:
        """Load and return the job template for this scheduler"""
        with open(load_template(template_file)) as f:
            return Template(f.read())
    
    def _estimate_nnodes(self, ncores):
        """Estimate number of nodes needed"""
        core_per_node = self.test_instance.config["hpc"]["core_per_node"]
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
        scaling = self.test_instance.config["scaling"]["strategy"]
        max_cores = self.test_instance.config["scaling"]["max_cores"]

        strategies = {
        "weak_3d": ScalingStrategy.weak_3d_scaling
        }

        if scaling not in strategies:
            raise ValueError(f"Unsupported scaling strategy: {scaling}")

        return strategies[scaling], max_cores
    
    @property
    def use_gpu(self):
        return self.test_instance.config["hpc"]["gpu_build"].upper() in {"CUDA", "HIP"}
    
    def _prepare_template_vars(self, test_item: dict, **job_params) -> dict:
        """Prepare common template variables used by all schedulers"""
        # get global hpc job settings
        global_hpc = self.test_instance.config["hpc"]

        # test specific vars
        koi = {"name", "target", "input_file"}
        test_var = {k: test_item[k] for k in koi if k in test_item}

        # Get test specific hpc settings if they are provided
        test_var.update(test_item.get("job_settings", {}))
        # update target value
        test_var["target"] = str(self.test_instance.repo_dir/"build/src/problems"/test_item["target"])
        
        # supplementary 
        sup = {
            "use_gpu": self.use_gpu,
            "use_partition": self.test_instance.config.get("partition") is not None,
        }

        # update job_params
        ncell_params = job_params.get("ncell_params")
        _core = job_params.get("core")
        ncell_args = "" if _core == 1 else ncell_params[[1]]

        # all settings 
        # notice test specific settings will overwrite global settings
        return {**global_hpc, **sup, **test_var, **job_params, "ncell_args": ncell_args}
    
    def render_single_job_script(self, test_item: dict, **job_params) -> str:
                
        # Get template variable value
        template_vars = self._prepare_template_vars(test_item, **job_params)
        # breakpoint()
        return self.template.render(**template_vars)
    
    def generate_all_job_scripts(self):
        """Generate all job scripts for all tests - shared logic across schedulers"""
        
        # get scaling strategy
        scaling_func, max_cores = self._get_scaling_strategy()

        # Initiate dataframe
        output = JobDataFrame(Job_FIELD)
        
        for test in self.test_instance.config["tests"]:
            input_file = str(self.test_instance.config["paths"]["test_inputs"] / test["input_file"])
            init_ncell = self._read_ncell(input_file)
            core_dict = scaling_func(init_ncell, max_cores)
            
            for core, arg_value in core_dict.items():
                node = self._estimate_nnodes(core)
                # create a directory for each test job
                result_dir = str(self.test_instance.result_dir_base / f"{test['name']}_n{core}")
                os.makedirs(result_dir, exist_ok=True)
                
                # Prepare job parameters
                job_params = {
                    'core': core,
                    'node': node,
                    'ncell_params': arg_value,
                    'input_file': input_file,
                    'result_dir': result_dir,
                }
                
                # Generate job script using scheduler-specific logic
                rendered = self.render_single_job_script(test, **job_params)
                
                job_name = result_dir + f"/{test['name']}_n{core}.sh"
                with open(job_name, "w") as f:
                    f.write(rendered)
                logger.info(f"✅ Job script generated: {job_name}")

                # Submit job using scheduler-specific method
                job_id = self.submit_job(job_name)
               
                # Record job information
                params = {
                    "test_name": test["name"],
                    "n_cell": arg_value[0],
                    "n_cores": core,
                    "cores_per_node": self.test_instance.config["hpc"]["core_per_node"],
                    "n_nodes": node,
                }
                output.add_job_entry(job_id=job_id, **params)
        
        # save dataframe
        output.save(self.test_instance.result_dir_base/"job_submission.parquet")
    
    
class SlurmScheduler(JobScheduler):
    """job scheduler implementation on HPC NT"""
    
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
        working_dir = self.config["paths"]["working_dir"] / "performance_test"
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
        hpc = self.config["hpc"]["cluster"].lower()
        
        schedulers = {
            "nt": [SlurmScheduler, "job_slurm.sh.j2"],
            "setonix": [SlurmScheduler, "job_setonix.sh.j2"],
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
    job_creator = JobCreator(config)
    job_creator.run_full_pipeline()
    
    
'''
class JobCreator:
    # templates to use
    BUILD_TEMPLATE = load_template("build_all.sh.j2")
    JOB_TEMPLATE = load_template("job_slurm.sh.j2")

    def __init__(self, config:dict):
        self.config = config
        self._prepare()
        self._add_gpu_build_dflag()
        self.core_per_node = config["core_per_node"]

    def _add_gpu_build_dflag(self):
        self.gpu_dflag = ""
        if self.config["gpu_build"] is None:
            pass
        elif self.config["gpu_build"].upper() == "CUDA":
            self.gpu_dflag = "-DAMReX_GPU_BACKEND=CUDA"
            
        elif self.config["gpu_build"].upper() == "HIP":
            self.gpu_dflag = "-DAMReX_GPU_BACKEND=HIP"

    
    def _estimate_nnodes(self, ncores):
        nnodes = (int(ncores) + int(self.core_per_node) - 1) // int(self.core_per_node)
        return nnodes
    
    def _set_timestamp(self):
        return datetime.today().strftime("%Y%m%d%H%M%S")
    
    def _make_dir(self, dir_path: Path, parents=True, exist_ok=True):
        try:
            dir_path.mkdir(parents=parents, exist_ok=exist_ok)
        except Exception as e:
            
            logger.error(f"Failed to create directory {dir_path}: {e}")
            sys.exit(1)
        return dir_path

    def _set_dirs(self):
        # get timestamp
        timestamp = self._set_timestamp()

        # layout dirs
        working_dir = self.config["paths"]["working_dir"]/"performance_test"
        self.test_instance = self._make_dir(working_dir/timestamp, parents=True, exist_ok=False)
        logger.info(f"Initialize test instance: {self.test_instance}")
        self.result_dir_base = self._make_dir(self.test_instance/"results", parents=True, exist_ok=False)
        logger.info(f"Create results directory: {self.result_dir_base}")
        self.repo_dir = self.test_instance/"quokka"

        

    def _prepare(self):
        # create and record dirs
        self._set_dirs()

        # write test instance meta yaml file
        write_test_instance_meta(self.config, self.test_instance)

        # add pipeline log handler
        LoggerManager.add_pipeline_log(self.test_instance)
        
    def get_job_id(self, submit_stdout):
        match = re.search(r"Submitted batch job (\d+)", submit_stdout)
        if match:
            job_id = match.group(1) 
        else: 
            job_id = None
        return job_id
    
    def _validate_path(self, path: Path) -> Path:
        if not path.exists():
            msg = f"{path} doesn't exist."
            logger.error(msg)
            raise FileNotFoundError(msg)  
        return path

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
        scaling = self.config["scaling"]["strategy"]
        max_cores = self.config["scaling"]["max_cores"]

        strategies = {
        "weak_3d": ScalingStrategy.weak_3d_scaling
        }

        if scaling not in strategies:
            raise ValueError(f"Unsupported scaling strategy: {scaling}")

        return strategies[scaling], max_cores

    def submit_job(self, jobfile:str):
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


    def generate_build_file(self) -> None:
        with open(self.BUILD_TEMPLATE) as f:
            build_temp = Template(f.read())

        re_build = build_temp.render(
        shell = self.config["shell"],
        test_instance = str(self.test_instance),
        env_setup_script = self.config["env"]["script"],
        tests = self.config["tests"],
        gpu_build_flag = self.gpu_dflag
        )
        build_file = self.test_instance/"build_all.sh"
        with open(build_file, "w") as f:
            f.write(re_build)
        logger.info("✅ Build script generated: build_all.sh")
        # Run the build script
        run_and_log_subprocess([self.config["shell"], build_file], logger=logger, batch_size=1)
        logger.info("Finish building the tests.")

    def _generate_job_script(self, job_template:Template, test_item:dict, 
                             input_file:str, result_dir:str, core:int, 
                             node:int, ncell_params:str):
        # get job info
        params = {
            "test_name": test_item["name"],
            "n_cell": ncell_params[0],
            "n_cores": core,
            "cores_per_node": self.core_per_node,
            "n_nodes": node,
        }
        
        # check whether the test is built using gpu
        use_gpu = len(self.gpu_dflag) != 0
        # disable ncell_param for a single core
        if core == 1:
            ncell_args = "" 
        else:
            ncell_args = ncell_params[1]
        # check wehther partition is chosen
        use_partition = self.config["partition"] is not None

        rendered = job_template.render(
                    shell=self.config["shell"],
                    env_setup_script = self.config["env"]["script"],
                    test_name = test_item["name"],
                    target=str(self.repo_dir/"build/src/problems"/test_item["target"]),
                    input_file=input_file,
                    result_dir = result_dir,
                    cores = core,
                    nodes = node,
                    cores_per_node = self.core_per_node,
                    time_limit = test_item["time_limit"],
                    memory = test_item["memory"],
                    runtime_args = ncell_args,
                    use_gpu = use_gpu,
                    use_partition = use_partition
                )
        
        return params, rendered

    def generate_job_scripts(self) -> None:

        # Load slurm job templates
        with open(self.JOB_TEMPLATE) as f:
            job_temp = Template(f.read())

        # get scaling strategy
        scaling_func, max_cores = self._get_scaling_strategy()

        # Initiate dataframe
        output = JobDataFrame(Job_FIELD)
        for test in self.config["tests"]:
            input_file = str(self.config["paths"]["test_inputs"]/test["input_file"])
            # get init n_cell
            init_ncell = self._read_ncell(input_file)
            core_dict = scaling_func(init_ncell, max_cores)
            for core, arg_value in core_dict.items():
                node = self._estimate_nnodes(core)
                # create a directory for each test job
                result_dir = str(self.result_dir_base/f"{test['name']}_n{core}")
                os.makedirs(result_dir, exist_ok=True)
                
                params, rendered = self._generate_job_script(job_temp, test, input_file, 
                                                     result_dir, core, node, arg_value)

                job_name = result_dir + f"/{test['name']}_n{core}.sh"
                with open(job_name, "w") as f:
                    f.write(rendered)
                logger.info(f"✅ Job script generated: {job_name}")
                # job_id = self.submit_job(job_name)
                output.add_job_entry(job_id=1, **params)
        
        # save dataframe 
        output.save(self.result_dir_base/"job_submission.parquet")
'''

   