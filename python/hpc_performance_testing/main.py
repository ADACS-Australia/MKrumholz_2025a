from hpc_performance_testing.logger import LoggerManager
from hpc_performance_testing.config import load_config, load_yaml
from hpc_performance_testing.utils import validate_path
from hpc_performance_testing.submit import JobCreator
from hpc_performance_testing.extract import JobResultExtractor, JobStatusChecker
from hpc_performance_testing.cleanup import TestInstanceCleanup

def _add_pipeline_handler(config: dict):
    test_instance_path = validate_path(config["runtime"]["test_instance"])
    LoggerManager.add_pipeline_log(test_instance_path)

def submit_jobs(config_file):
    config = load_config(config_file)
    job_creator = JobCreator(config)
    job_creator.run_full_pipeline()

def check_jobs(test_instance_config_file):
    config = load_yaml(test_instance_config_file)
    _add_pipeline_handler(config)
    checker = JobStatusChecker(config)
    status = checker.check_jobs()
    return status

def extract_results(output_config_file):
    config = load_yaml(output_config_file)
    _add_pipeline_handler(config)
    result = JobResultExtractor(config)
    result.get_job_results()

def cleanup(scenario="resubmit"): # allowed actions: resubmit, finished, delete_all
    cleanup = TestInstanceCleanup()
    res = cleanup.apply(scenario)
    print(res)



if __name__ == "__main__":
    # submit_jobs("config_nt.yaml")
    submit_jobs("config.yaml")
    # status = check_jobs("test_instance.yaml")
    # extract_results("test_instance.yaml")
    # cleanup()