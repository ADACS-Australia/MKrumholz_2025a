from pathlib import Path

from hpc_performance_testing.utils import validate_path
from hpc_performance_testing.patterns import JOB_OUTPUT_NAME
from hpc_performance_testing.parser import JobOutput
from hpc_performance_testing.output import Job_output_FIELD, JobDataFrame
from hpc_performance_testing.config import load_config

class JobResultExtractor:
    def __init__(self, test_instance_config: dict):
        self.config = test_instance_config

    def _find_job_output_files(self):
        root_path = validate_path(Path(config["runtime"]["test_instance"])/"results")
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
        result = JobDataFrame(Job_output_FIELD)

        for f in file_list:
            data_dict = self._process_job_output_files(f, Job_output_FIELD)
            result.add_job_entry(**data_dict)
        
        # save the results as parquet
        result.save(self.root_path/"job_output.parquet")


   




if __name__ == "__main__":
    config = load_config("test_instance.yaml")
    extractor = JobResultExtractor(config)
    extractor.get_job_results()
    # breakpoint()