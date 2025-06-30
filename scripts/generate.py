import os
import stat
from pathlib import Path
import subprocess
import re
import yaml
from jinja2 import Template
# import numpy as np

from datetime import datetime

# Util: resolve the path
def resolve_path(path: str):
    # resolve environment variable and ~
    expanded = os.path.expanduser(os.path.expandvars(path))
    return Path(expanded).resolve()

# Util: change to executables
def make_executable(file:str) -> None:
    os.chmod(file, os.stat(file).st_mode | stat.S_IXUSR)

# Load config
def load_config(file="config.yaml"):
    with open(file) as f:
        config = yaml.safe_load(f)

    # resolve paths
    for key, path_value in config["paths"].items():
        config["paths"][key] = resolve_path(path_value)

    # validation
    # check wether env script exists
    env_script = resolve_path(config["env"]["script"])

    if not env_script.exists():
        raise FileNotFoundError(f"Environment script {env_script} is not found.")

    return config


class JobController:
    # templates to use
    BUILD_TEMPLATE = "templates/build_all.sh.j2"
    JOB_TEMPLATE = "templates/job_slurm.sh.j2"

    def __init__(self, config:dict):
        self.config = config
        self._add_gpu_build_dflag()
        self._set_timestamp()
        self._set_paths()

    def _add_gpu_build_dflag(self):
        self.gpu_dflag = ""

        if self.config["gpu_build"] is None:
            pass
        elif self.config["gpu_build"].upper == "CUDA":
            self.gpu_dflag = "-DAMReX_GPU_BACKEND=CUDA"
        elif self.config["gpu_build"].upper == "HIP":
            self.gpu_dflag = "-DAMReX_GPU_BACKEND=HIP"
        
    
    def _set_timestamp(self):
        self.timestamp = datetime.today().strftime("%Y%m%d%H%M%S")

    def _set_paths(self):
        self.working_dir = config["paths"]["working_dir"]/"performance_test"
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
        shell = config["shell"],
        working_dir = str(self.working_dir),
        test_instance = str(self.test_instance),
        env_setup_script = config["env"]["script"],
        tests = config["tests"],
        gpu_build_flag = self.gpu_dflag
        )
        with open("build_all.sh", "w") as f:
            f.write(re_build)
        print("✅ Build script generated: build_all.sh")

        # Run the build script
        try:
            subprocess.run([config["shell"], "build_all.sh"], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print("Build failed! \n")
            print("stderr: {}".format(e.stderr))
            exit(1)
        print("Finish building the tests.")

    def _generate_job_script(self, job_template:Template, test_item:dict, 
                             input_file:str, result_dir:str, core:int,
                             ncell_params:str):
        # check whether the test is built using gpu
        use_gpu = len(self.gpu_dflag) != 0

        # disable ncell_param for a single core
        if core == 1:
            ncell_params = ""

        rendered = job_template.render(
                    shell=config["shell"],
                    env_setup_script = config["env"]["script"],
                    test_name = test_item["name"],
                    target=str(self.repo_dir/"build/src/problems"/test_item["target"]),
                    input_file=input_file,
                    result_dir = result_dir,
                    cores=core,
                    time_limit=test_item["time_limit"],
                    memory=test_item["memory"],
                    runtime_args = ncell_params,
                    use_gpu = use_gpu
                )
        
        return rendered

    def generate_job_scripts(self) -> None:

        # Load slurm job templates
        with open(self.JOB_TEMPLATE) as f:
            job_temp = Template(f.read())

        # get scaling strategy
        scaling_func, max_cores = self._get_scaling_strategy()
        for test in config["tests"]:
            input_file = str(self.config["paths"]["test_inputs"]/test["input_file"])
            # get init n_cell
            init_ncell = self._read_ncell(input_file)
            core_dict = scaling_func(init_ncell, max_cores)

            for core, arg_value in core_dict.items():
                # create a directory for each test job
                result_dir = str(self.result_dir_base/f"{test['name']}_n{core}")
                os.makedirs(result_dir, exist_ok=True)
                # rendered = job_temp.render(
                #     shell=config["shell"],
                #     env_setup_script = config["env"]["script"],
                #     test_name = test["name"],
                #     target=str(self.repo_dir/"build/src/problems"/test["target"]),
                #     input_file=input_file,
                #     result_dir = result_dir,
                #     cores=core,
                #     time_limit=test["time_limit"],
                #     memory=test["memory"],
                #     runtime_args = arg_value
                # )
                rendered = self._generate_job_script(job_temp, test, input_file, 
                                                     result_dir, core, arg_value)

                job_name = result_dir + f"/{test['name']}_n{core}.sh"
                with open(job_name, "w") as f:
                    f.write(rendered)
                print(f"✅ Job script generated: {job_name}")
                job_id = self.submit_job(job_name)


class ScalingStrategy:

    @classmethod
    def _convert_to_amr_param(cls, box: list) -> str:
        value = " ".join(str(x) for x in box)
        return f'amr.n_cell={value}'
    
    @classmethod
    def weak_3d_scaling(cls, init_box:list, max_cores: int):
        dim = len(init_box) #todo: raise error when it's zero 
        core_dict = {}
        cores = 1
        while cores**dim <= max_cores:
            box = init_box[:]
            box = [x * 2 for x in box]
            core_dict[cores] = cls._convert_to_amr_param(box)
            cores *= 2

        return core_dict



if __name__ == "__main__":
    config = load_config()
    jobs = JobController(config)
    jobs.generate_build_file()
    jobs.generate_job_scripts()

   