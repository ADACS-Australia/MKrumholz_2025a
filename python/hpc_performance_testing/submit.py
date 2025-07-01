import os

from pathlib import Path
import subprocess
import re
from datetime import datetime
from jinja2 import Template

from hpc_performance_testing.strategy import ScalingStrategy
from hpc_performance_testing.output import Job_FIELD, JobDataFrame

class JobCreator:
    # templates to use
    BUILD_TEMPLATE = "templates/build_all.sh.j2"
    JOB_TEMPLATE = "templates/job_slurm.sh.j2"

    def __init__(self, config:dict):
        self.config = config
        self._add_gpu_build_dflag()
        self.core_per_node = config["core_per_node"]
        self._set_timestamp()
        self._set_paths()

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
        self.timestamp = datetime.today().strftime("%Y%m%d%H%M%S")

    def _set_paths(self):
        self.working_dir = self.config["paths"]["working_dir"]/"performance_test"
        self.test_instance = self.working_dir/self.timestamp
        self.repo_dir = self.test_instance/"quokka"
        self.result_dir_base = self.test_instance/"results"

    def get_job_id(self, submit_stdout):
        match = re.search(r"Submitted batch job (\d+)", submit_stdout)
        if match:
            job_id = match.group(1) 
        else: 
            job_id = None
        return job_id
    
    def _validate_path(self, path: Path) -> Path:
        if not path.exists():
            raise FileNotFoundError(f"{path} doesn't exist.")  
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
            print("Submit job: {} \n".format(job_id))
        except subprocess.CalledProcessError as e:
            print("Job submission failed! \n")
            print("stderr: {}".format(e.stderr))
            exit(1)
        return job_id


    def generate_build_file(self) -> None:
        with open(self.BUILD_TEMPLATE) as f:
            build_temp = Template(f.read())

        re_build = build_temp.render(
        shell = self.config["shell"],
        working_dir = str(self.working_dir),
        test_instance = str(self.test_instance),
        env_setup_script = self.config["env"]["script"],
        tests = self.config["tests"],
        gpu_build_flag = self.gpu_dflag
        )
        with open("build_all.sh", "w") as f:
            f.write(re_build)
        print("✅ Build script generated: build_all.sh")

        # Run the build script
        try:
            subprocess.run([self.config["shell"], "build_all.sh"], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print("Build failed! \n")
            print("stderr: {}".format(e.stderr))
            exit(1)
        print("Finish building the tests.")

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
                print(f"✅ Job script generated: {job_name}")
                # job_id = self.submit_job(job_name)
                output.add_job_entry(job_id=1, **params)
        
        # save dataframe 
        output.save(self.result_dir_base/"job_submission.parquet")


# if __name__ == "__main__":
    # config = load_config()
    # jobs = JobController(config)
    # jobs.generate_build_file()
    # jobs.generate_job_scripts()

   