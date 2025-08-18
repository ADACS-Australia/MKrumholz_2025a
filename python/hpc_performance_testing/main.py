from hpc_performance_testing.config import load_config
from hpc_performance_testing.submit import JobCreator
from hpc_performance_testing.extract import JobResultExtractor, JobStatusChecker

def submit_jobs(config_file):
    config = load_config(config_file)
    job_creator = JobCreator(config)
    job_creator.run_full_pipeline()

def check_jobs(test_instance_config_file):
    config = load_config(test_instance_config_file)
    checker = JobStatusChecker(config)
    status = checker.check_job_list_status_slurm()
    return status

def extract_results(output_config_file):
    config = load_config(output_config_file)
    result = JobResultExtractor(config)
    result.get_job_results()

    # merge job and results dataframe




if __name__ == "__main__":
    submit_jobs("config_nt.yaml")
    # submit_jobs("config.yaml")
    # status = check_jobs("test_instance.yaml")
    # extract_results("test_instance.yaml")