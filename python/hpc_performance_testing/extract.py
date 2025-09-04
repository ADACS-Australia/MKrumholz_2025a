from pathlib import Path
import subprocess
from enum import Enum
from abc import ABC, abstractmethod
from typing import Optional, Dict
import re
import pandas as pd

from hpc_performance_testing.logger import LoggerManager
from hpc_performance_testing.utils import validate_path
from hpc_performance_testing.patterns import JOB_OUTPUT_NAME
from hpc_performance_testing.parser import JobOutput
from hpc_performance_testing.output import Job_output_FIELD, Job_status_FIELD, JobDataFrame
from hpc_performance_testing.config import load_yaml

logger = LoggerManager.get_logger()
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
        logger.info("Create Pandas DataFrame to store results.")
        for f in file_list:
            data_dict = self._process_job_output_files(f, Job_output_FIELD)
            result.add_job_entry(**data_dict)
            logger.info(f"Extract result from {f}.")
        # save the results as parquet
        result.save(self.root_path/"job_output.parquet")
        logger.info("Save results into parquet.")

class JobStatus(Enum):
    WAIT = "WAIT"
    FINISHED = "FINISHED"

class JobMonitorBase(ABC):
    @classmethod
    @abstractmethod
    def check_active_job(cls, job_id: str):
        """Check whether a job is active: in queue or running"""
        pass
    
    @classmethod
    @abstractmethod
    def retrieve_finished_job(cls, job_id: str):
        """Get job status of a finished job"""
        pass

class SlurmJobMonitor(JobMonitorBase):
    @classmethod
    def check_active_job(cls, job_id: str):
        try:
            queue = subprocess.run(["squeue", "-j", str(job_id)],
                                   capture_output=True,
                                   text=True,
                                   check=True)
            return queue
        except subprocess.CalledProcessError as e:
            logger.info(f"Job {job_id} is no longer in queue.")
            return None
    
    @classmethod
    def retrieve_finished_job(cls, job_id: str):
        try:
            result = subprocess.run(
                ["sacct", "-j", str(job_id), "-n", "-o", "JobID,State,ExitCode"],
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
            logger.error(f"'sacct' exits with error: {e}")
            return None

class PbsJobMonitor(JobMonitorBase):
    @classmethod
    def check_active_job(cls, job_id: str):
        try:
            # qstat returns non-zero when job is finished or unknown
            queue = subprocess.run(
                ["qstat", str(job_id)],
                capture_output=True,
                text=True,
                check=True
            )
            return queue  

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip()
            if "Job has finished" in stderr:
                logger.info(f"Job {job_id} has finished (not in queue).")
            elif "Unknown Job Id" in stderr:
                logger.info(f"Job {job_id} not found (possibly too old).")
            else:
                logger.error(f"qstat returned error for job {job_id}: {stderr}")
            return None
        
    @staticmethod
    def _parse_qstat_fx(stdout: str) -> Optional[Dict[str, str]]:
        
        m_state = re.search(r'(?m)^\s*job_state\s*=\s*([A-Z])\s*$', stdout)
        m_exit  = re.search(r'(?m)^\s*Exit_status\s*=\s*(-?\d+)\s*$', stdout)

        state = m_state.group(1) if m_state else "UNKNOWN"
        exit_code = m_exit.group(1) if m_exit else "UNKNOWN"
        return state, exit_code
    
    @classmethod    
    def retrieve_finished_job(cls, job_id: str):
        try:
            result = subprocess.run(
                ["qstat", "-fx", str(job_id)],
                capture_output=True,
                text=True,
                check=True
            )
            state, exit_code = cls._parse_qstat_fx(result.stdout)
            return {"job_id": job_id, "state": state, "exit_code": exit_code}

        except subprocess.CalledProcessError as e:
            print(f"'qstat -fx' exits with error: {e}")
            return None

class JobStatusChecker:

    def __init__(self, test_instance_config: dict):
        self.config = test_instance_config
        self.scheduler = self._get_scheduler()
        self.output_file = self.config["runtime"]["test_instance"] + "/results/job_exit_status.parquet"

    def _get_scheduler(self):
        return self.config["hpc"]["scheduler"]

    def _get_job_monitor(self):
        if self.scheduler.lower() == "slurm":
            return SlurmJobMonitor
        if self.scheduler.lower() == "pbs":
            return PbsJobMonitor
        else:
            raise NotImplementedError(f"HPC with scheduler {self.scheduler} is not supported yet. Only PBS and SLURM are supported.")
        
    def _get_submitted_jobs(self) -> list:
        """read from job submission parquet"""
        job_submission_parquet = validate_path(self.config["runtime"]["test_instance"]+"/results/job_submission.parquet")
        df = pd.read_parquet(job_submission_parquet)
        return df["job_id"].astype(str).tolist()
    
    def _init_output(self):
        if not Path(self.output_file).exists():
            return JobDataFrame(fields=Job_status_FIELD)
        else:
            df = pd.read_parquet(self.output_file)
            return JobDataFrame.from_df(df=df, fields=Job_status_FIELD)
            
    def check_jobs(self) -> JobStatus:
        jobs = self._get_submitted_jobs()
        jmonitor = self._get_job_monitor()

        active_jobs = [job for job in jobs if jmonitor.check_active_job(job)]
        _active_set = set(active_jobs)
        finished_jobs = [job for job in jobs if job not in _active_set]

        if finished_jobs:
            output = self._init_output()
            recorded = output.job_list
            _recorded_set = set(recorded)
            unrecorded_fin = [job for job in finished_jobs if job not in _recorded_set]

            if unrecorded_fin:

                for job in unrecorded_fin:

                    job_status = jmonitor.retrieve_finished_job(job)
                    if job_status is not None:
                        output.add_job_entry(**job_status)
                        logger.info(f"Job {job} is finished with status {job_status}.")

                output.save(self.output_file)


        if active_jobs:
            # At least one job is still pending or running
            return JobStatus.WAIT
        
        return JobStatus.FINISHED
    
if __name__ == "__main__":
    config = load_yaml("test_instance.yaml")
    # breakpoint()
    checker = JobStatusChecker(config)
    breakpoint()
    status = checker.check_jobs()
    # extractor = JobResultExtractor(config)
    # extractor.get_job_results()
    # breakpoint()