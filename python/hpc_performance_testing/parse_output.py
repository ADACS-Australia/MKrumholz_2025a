from pathlib import Path
import re

from hpc_performance_testing.utils import validate_path
from hpc_performance_testing.patterns import *

class ProfileParser:
    
    def __init__(self, profile_file: Path | str ):
        profile_file = validate_path(profile_file)
        self._read_file(profile_file)
        
    def _read_file(self, filename):
        with open(filename) as f:
            content = f.read()
        self.content = content

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

if __name__ == "__main__":
    parser = ProfileParser("test_hydro3d_blast_gpu_n8_v2_1902441.out")
    parser.get_zone_update_info()
    parser.get_elapse_time()
