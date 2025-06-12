import os
import stat
from pathlib import Path
import yaml
from jinja2 import Template

from datetime import datetime

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# convert the working dir to absolute path
working_dir = Path(config["paths"]["working_dir"]).resolve()

# Setup date time
timestamp = datetime.today().strftime("%Y%m%d")

# Load build template
with open("templates/build_all.sh.j2") as f:
    build_temp = Template(f.read())

# Load slurm job templates
with open("templates/job_slurm.sh.j2") as f:
    template = Template(f.read())


# --- Generate build script ---
re_build = build_temp.render(
    shell = config["shell"],
    working_dir = str(working_dir),
    test_dir = str(working_dir/timestamp),
    env_setup_script = config["env"]["script"],
    tests = config["tests"],
    cmake_cache = config
)
with open("build_all.sh", "w") as f:
    f.write(re_build)
os.chmod("build_all.sh", os.stat("build_all.sh").st_mode | stat.S_IXUSR)
print("✅ Build script generated: build_all.sh")

# --- Generate job scripts ---
source_dir = working_dir/timestamp/"quokka"

with open("submit_jobs.sh", "w") as fjob:
    for test in config["tests"]:
        for core in test["cores"]:
            # create a directory for each test job
            result_dir = str(working_dir/"results"/f"{test['name']}_n{core}")
            os.makedirs(result_dir, exist_ok=True)
            rendered = template.render(
                shell=config["shell"],
                env_setup_script = config["env"]["script"],
                source_dir=str(source_dir),
                build_dir=str(source_dir/"build"),
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
            os.chmod(job_name, os.stat(job_name).st_mode | stat.S_IXUSR)
            print(f"✅ Job script generated: {job_name}")
            fjob.write(f"sbatch {job_name} \n")

os.chmod("submit_jobs.sh", os.stat("submit_jobs.sh").st_mode | stat.S_IXUSR)
print("✅ Job submission script generated: submit_jobs.sh")