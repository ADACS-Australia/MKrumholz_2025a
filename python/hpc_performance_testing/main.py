from hpc_performance_testing.config import load_config
from hpc_performance_testing.submit import JobCreator

def submit_jobs(config_file):
    config = load_config(config_file)
    job = JobCreator(config)
    job.generate_build_file()
    job.generate_job_scripts()


if __name__ == "__main__":
    submit_jobs("config.yaml")