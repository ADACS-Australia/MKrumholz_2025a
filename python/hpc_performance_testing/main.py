from hpc_performance_testing.config import load_config
from hpc_performance_testing.submit import JobCreator
from hpc_performance_testing.extract import JobResultExtractor

def submit_jobs(config_file):
    config = load_config(config_file)
    job = JobCreator(config)
    # job.generate_build_file()
    job.generate_job_scripts()

def extract_results(output_config_file):
    config = load_config(output_config_file)
    result = JobResultExtractor(config)
    result.get_job_results()

    # merge job and results dataframe
    



if __name__ == "__main__":
    # submit_jobs("config.yaml")
    extract_results("test_instance.yaml")