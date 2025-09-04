from pathlib import Path
import re
from io import StringIO
import pandas as pd

from hpc_performance_testing.logger import LoggerManager
from hpc_performance_testing.utils import validate_path, flatten_dict
from hpc_performance_testing.patterns import *

logger = LoggerManager.get_logger()

class JobOutputParser:
    # available table headers
    profile_table = {
        "timing_inclusive": TIMING_INCLUSIVE,
        "timing_exclusive": TIMING_EXCLUSIVE
    }
    
    def __init__(self, job_output_file: Path | str):
        job_output_file = validate_path(job_output_file)
        self.init_parse(job_output_file)
        
    def _read_file(self, filename):
        with open(filename) as f:
            content = f.read()
        self.content = content

    def _read_job_id(self, job_output_file):
        job_id = self.parse_lines(str(job_output_file), JOB_OUTPUT_NAME)
        assert job_id is not None, "Can't read Job ID from output filename; check relevant jinja template and regex patterns to debug"
        self.job_id = job_id

    def _extract_region_blocks(self):
        self.region_blocks = re.findall(r'BEGIN REGION.*?END REGION', self.content, flags=re.DOTALL)
        self.non_region_content = re.sub(r'BEGIN REGION.*?END REGION', '', self.content, flags=re.DOTALL)

    def init_parse(self, job_output_file):
        self._read_file(job_output_file)
        self._read_job_id(job_output_file)
        self._extract_region_blocks()


    def parse_lines(self, text: str, pattern: re.Pattern | str):
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        
        n_groups = pattern.groups
        if n_groups == 0:
            raise ValueError("Regex has no capturing groups; expected at least one.")
        
        groupdict_rev = {idx: name for name, idx in pattern.groupindex.items()}
        keys = [groupdict_rev.get(i, f"group{i}") for i in range(1, n_groups + 1)]
        
        match = pattern.search(text)

        if not match:
            logger.warning(f"No match found for {keys}")
            if n_groups == 1:
                return None
            return {key: None for key in keys}
        
        # if match
        values = match.groups()

        if n_groups == 1:
            return values[0]
        
        return dict(zip(keys, values))
          

    def _extract_table(self, text: str, table_regex: re.Pattern | str):
        if isinstance(table_regex, str):
            table_regex = re.compile(table_regex)
        assert table_regex.groups == 2, "The table regex should contain two groups: header and data"
        
        match = table_regex.search(text)

        if not match:
            logger.warning("Table block not found with full table structure.")
            return None
        
        header = match.group(1).strip()
        data_block = match.group(2).strip()
        
        # Combine header and data for read_fwf
        table_text = header + "\n" + data_block
        try:
            df = pd.read_fwf(StringIO(table_text))
        except Exception as e:
            raise IOError(f"Can't read table text to dataframe: {e}. Check whether the table has fixed length.")
        
        return df
        
    def _validate_df_dict(self, df: pd.DataFrame):
        assert isinstance(df, pd.DataFrame), "Input df should be of type Pandas.DataFrame"
        list_dict = df.to_dict(orient="records")
        n_entry = len(list_dict)
        assert n_entry == 1, f"There should be just one entry of the same function name in the table. Found {n_entry}."
        return list_dict[0] or {}
               
    def read_tinyprofiler_function_stats(self, text: str, table_name: str, function_name: str, column_name : str | list | None = None) -> dict | None:
        assert table_name in self.profile_table.keys(), f"The table {table_name} doesn't exist or its regex is not added. Available tables: {self.profile_table.keys()}"
        table_regex = self.profile_table[table_name]
        
        assert table_regex is not None
        df = self._extract_table(text, table_regex)

        if df is None or df.empty:
            logger.warning(f"Table {table_name} is empty or can't be extracted.")
            return {}

        if "Name" not in df.columns:
            raise ValueError("The column `Name` does not exist! Check the tiny profiler output.")
        
        assert function_name in df["Name"].values, f"Function name '{function_name}' not found in table. Check whether it's spelled correctly."

        # Filter by function name first
        filtered_df = df[df["Name"] == function_name]
        
        if column_name is None:
            return self._validate_df_dict(filtered_df)

        # Validate column names
        columns_to_check = [column_name] if isinstance(column_name, str) else column_name
        columns_to_check.append("Name") # make sure the function name is in the output
        columns_to_check = list(set(columns_to_check))
        missing_cols = [col for col in columns_to_check if col not in df.columns]
        assert not missing_cols, f"Column(s) not in DataFrame: {missing_cols}"
        
        return self._validate_df_dict(filtered_df[columns_to_check])       
   
class JobOutput:
    def __init__(self, job_output_file: Path | str):
        self.parser = JobOutputParser(job_output_file)

    def _available_properties(self) -> list[str]:
        return [
            name for name in dir(self.__class__)
            if isinstance(getattr(self.__class__, name, None), property)
            and not name.startswith("_")
        ]

    @property
    def job_id(self):
        return self.parser.job_id
    
    @property
    def n_mpi_processes(self):
        return self.parser.parse_lines(self.parser.content, N_MPI_PROCESS)
    
    @property
    def zone_update(self):
        return self.parser.parse_lines(self.parser.content, ZONE_UPDATE_RATE)
    @property
    def elapse_time(self):
        return self.parser.parse_lines(self.parser.content, ELAPSED_TIME)
    
    @property
    def boundary_condition_inc_main(self):
        return self.parser.read_tinyprofiler_function_stats(self.parser.non_region_content,
                                                            "timing_inclusive", 
                                                            "AMRSimulation::fillBoundaryConditions()")

    def extract_job_output(self, field_names: str | list[str] | dict) -> dict:
        
        # validate inputs
        if isinstance(field_names, str):
            field_names = [field_names]
        elif isinstance(field_names, dict):
            field_names = list(field_names.keys())

        if not isinstance(field_names, list):
            raise TypeError(f"Field names must be of type str, list[str] or dict; {field_names} is of type {type(field_names)}")
        
        if not all(isinstance(name, str) for name in field_names):
            bad = [type(name).__name__ for name in field_names if not isinstance(name, str)]
            raise TypeError(f"All field names must be strings; got invalid types: {bad}")
        
        extract_dict = {}

        for field in field_names:
            # validate 
            attr = getattr(self.__class__, field, None)
            if not isinstance(attr, property):
                avail_props = self._available_properties() 
                raise AttributeError(f"'{field}' is not a property of {self.__class__.__name__}. \n"
                                     f"Available properties: {avail_props}")
            
            # extract data
            extract_dict[field] = getattr(self, field)
        # breakpoint()

        return flatten_dict(extract_dict)


if __name__ == "__main__":
    parser = JobOutputParser("test_hydro3d_blast_gpu_n8_v2_JobID_1902441.out") 
    reader = JobOutput("test_hydro3d_blast_n8_JobID_2165884.out")
    res = reader.extract_job_output(["elapse_time", "zone_update"])
    # breakpoint()
    
