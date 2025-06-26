import os
import stat
from pathlib import Path
import yaml
from jinja2 import Template

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

    return config

with open("config.yaml") as f:
    config = yaml.safe_load(f)

# convert the working dir to absolute path
working_dir = Path(config["paths"]["working_dir"]).resolve()

# Setup date time
timestamp = datetime.today().strftime("%Y%m%d%H%M%S")

# Load slurm job templates
with open("templates/job_slurm.sh.j2") as f:
    template = Template(f.read())

def generate_build_file(config: dict, template="templates/build_all.sh.j2",output="build_all.sh") -> None:

    with open(template) as f:
        build_temp = Template(f.read())

    re_build = build_temp.render(
    shell = config["shell"],
    working_dir = str(working_dir),
    test_dir = str(working_dir/timestamp),
    env_setup_script = config["env"]["script"],
    tests = config["tests"],
    cmake_cache = config
    )
    with open(output, "w") as f:
        f.write(re_build)
    make_executable(output)
    print("✅ Build script generated: build_all.sh")

def generate_job_scripts(config: dict, template="templates/job_slurm.sh.j2") -> None:

    source_dir = working_dir/timestamp/"quokka"

    # Load slurm job templates
    with open(template) as f:
        job_temp = Template(f.read())

    with open("submit_jobs.sh", "w") as fjob:
        for test in config["tests"]:
            for core in test["cores"]:
                # create a directory for each test job
                result_dir = str(working_dir/timestamp/"results"/f"{test['name']}_n{core}")
                os.makedirs(result_dir, exist_ok=True)
                rendered = job_temp.render(
                    shell=config["shell"],
                    env_setup_script = config["env"]["script"],
                    source_dir=str(source_dir),
                    target_dir=str(source_dir/"build/src/problems"),
                    test_in_dir=str(source_dir/"tests"),
                    result_dir = result_dir,
                    test_name=test["name"],
                    target=test["target"],
                    input_file=test["input_file"],
                    cores=core,
                    time_limit=test["time_limit"],
                    memory=test["memory"]
                )

                job_name = result_dir + f"/{test['name']}_n{core}.sh"
                with open(job_name, "w") as f:
                    f.write(rendered)
                make_executable(job_name)
                print(f"✅ Job script generated: {job_name}")
                fjob.write(f"sbatch {job_name} \n")

    make_executable("submit_jobs.sh")
    print("✅ Job submission script generated: submit_jobs.sh")

if __name__ == "__main__":
    config = load_config()
    generate_build_file(config=config)
    generate_job_scripts(config=config)