import re
from patterns import *


def get_zone_update_info(outfile):
    microseconds_per_update = None
    megaupdates_per_second = None
    n_process = None
    with open(outfile) as f:
        content = f.read()
        
        match_performance = RE_ZONE_UPDATE_RATE.search(content)

        if match_performance:
            microseconds_per_update = float(match_performance.group(1))   
            megaupdates_per_second = float(match_performance.group(2))  

        match_np = RE_N_MPI_PROCESS.search(content)
        if match_np:
            n_process = int(match_np.group(1))
    print(microseconds_per_update, megaupdates_per_second, n_process)

if __name__ == "__main__":
    get_zone_update_info("test_hydro3d_blast_gpu_n8_v2_1683814.out")
