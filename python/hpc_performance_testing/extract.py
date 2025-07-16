from pathlib import Path
import subprocess
import pandas as pd

from hpc_performance_testing.utils import validate_path
from hpc_performance_testing.patterns import JOB_OUTPUT_NAME
from hpc_performance_testing.parser import JobOutput
from hpc_performance_testing.output import Job_output_FIELD, JobDataFrame
from hpc_performance_testing.config import load_config

class JobResultExtractor:
    def __init__(self, test_instance_config: dict):
        self.config = test_instance_config

    def _find_job_output_files(self):
        root_path = validate_path(Path(self.config["runtime"]["test_instance"])/"results")
        self.root_path = root_path
        
        return [
            f for f in root_path.rglob("*")
            if f.is_file() and JOB_OUTPUT_NAME.search(f.name)
        ]
    

    def _process_job_output_files(self, output_file: str | Path, field_names):
        output = JobOutput(output_file)
        field_dict = output.extract_job_output(field_names)

        return field_dict

    def get_job_results(self):
        file_list = self._find_job_output_files()

        # construct a result dataframe
        result = JobDataFrame()

        for f in file_list:
            data_dict = self._process_job_output_files(f, Job_output_FIELD)
            result.add_job_entry(**data_dict)
    
        # save the results as parquet
        result.save(self.root_path/"job_output.parquet")


   
class JobStatusChecker:

    def __init__(self, test_instance_config: dict):
        self.config = test_instance_config

    @classmethod
    def _get_job_exit_code_slurm(cls, job_id: str):
        try:
            result = subprocess.run(
                ["sacct", "-j", job_id, "-n", "-o", "JobID,State,ExitCode"],
                capture_output=True,
                text=True,
                check=True
            )

            for line in result.stdout.strip().splitlines():
                parts = line.strip().split()
                if len(parts) < 3:
                    continue
                jid, state, exit_code = parts[0], parts[1], parts[2]
                if jid == job_id:  # exact match
                    return {"job_id": job_id, "state": state, "exit_code": exit_code}
            return None

        except subprocess.CalledProcessError as e:
            print(f"'sacct' exits with error: {e}")
            return None

    @classmethod
    def _check_slurm_job_queue(cls, job_id: str):
        try:
            queue = subprocess.run(["squeue", "-j", job_id],
                                   cpature_output=True,
                                   text=True,
                                   check=True)
            return queue
        except subprocess.CalledProcessError as e:
            print(f"Job {job_id} is no longer in queue.")
            return None

    def _get_submitted_jobs(self):
        """read from job submission parquet"""
        job_submission_parquet = validate_path(self.config["runtime"]["test_instance"]+"/results/job_submission.parquet")
        df = pd.read_parquet(job_submission_parquet)
        return df["job_id"].tolist()
    
    def check_job_list_status_slurm(self):
        jobs = self._get_submitted_jobs()
        res = []
        for job in jobs:
            check_queue = self._check_slurm_job_queue(job)
            if check_queue is not None:
                return None
            job_status = self._get_job_exit_code_slurm(job)
            if job_status is not None:
                res.append(job_status)
        return res


if __name__ == "__main__":
    config = load_config("test_instance.yaml")
    checker = JobStatusChecker(config)
    checker.check_job_list_status_slurm()
    # extractor = JobResultExtractor(config)
    # extractor.get_job_results()
    # breakpoint()