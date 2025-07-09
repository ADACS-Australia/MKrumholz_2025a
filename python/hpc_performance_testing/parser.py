from pathlib import Path
import re
from io import StringIO
import pandas as pd

from hpc_performance_testing.utils import validate_path
from hpc_performance_testing.patterns import *

class JobOutputParser:
    # available table headers
    profile_table = {
        "timing_inclusive": TIMING_INCLUSIVE,
        "timing_exclusive": TIMING_EXCLUSIVE
    }
    
    def __init__(self, job_output_file: Path | str):
        job_output_file = validate_path(job_output_file)
        self._read_file(job_output_file)
        
    def _read_file(self, filename):
        with open(filename) as f:
            content = f.read()
        self.content = content

    def _read_job_id(self, job_output_file):
        job_id = -1 


    def _extract_region_blocks(self):
        self.region_blocks = re.findall(r'BEGIN REGION.*?END REGION', self.content, flags=re.DOTALL)
        self.non_region_content = re.sub(r'BEGIN REGION.*?END REGION', '', self.content, flags=re.DOTALL)

    def _parse_lines(self, text: str, pattern: re.Pattern | str):
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        pass

    def _extract_table(self, text: str, table_regex: re.Pattern | str):
        if isinstance(table_regex, str):
            table_regex = re.compile(table_regex)
        assert table_regex.groups == 2, "The table regex should contain two groups: header and data"
        
        match = table_regex.search(text)

        if not match:
            print("Table block not found with full table structure.")
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
        
            
    
    def _read_tinyprofiler_function_stats(self, text: str, table_name: str, function_name: str, column_name : str | list | None = None):
        if not table_name in self.profile_table.keys():
            print(f"The table {table_name} does not exist!")
            return None
        columns_regex = self.profile_table[table_name]
        df = self._extract_table(text, columns_regex)
        if column_name is None:
            return df[df["Name"] == function_name]
        else:    
            return df[df["Name"] == function_name][column_name]

    def get_zone_update_info(self):
        microseconds_per_update = None
        megaupdates_per_second = None
        n_process = None
 
        match_performance = RE_ZONE_UPDATE_RATE.search(self.content)

        if match_performance:
            microseconds_per_update = float(match_performance.group(1))   
            megaupdates_per_second = float(match_performance.group(2))  

        match_np = RE_N_MPI_PROCESS.search(self.content)
        if match_np:
            n_process = int(match_np.group(1))
        print(microseconds_per_update, megaupdates_per_second, n_process)

    def get_elapse_time(self):
        elapse_time = None
        match_et = ELPASE_TIME.search(self.content)
        if match_et:
            elapse_time = float(match_et.group(1))
        print(f"elapse time: {elapse_time}")
        return elapse_time
    
    def get_boundary_condition_stats(self):
        df = self._read_tinyprofiler_function_stats(self.non_region_content, "timing_inclusive", "AMRSimulation::fillBoundaryConditions()")
        print("boundary condition stats: ", df.to_string())
    
        
    

if __name__ == "__main__":
    parser = JobOutputParser("test_hydro3d_blast_gpu_n8_v2_1902441.out")
    parser.get_zone_update_info()
    parser.get_elapse_time()
    parser._extract_region_blocks()
    parser.get_boundary_condition_stats()
