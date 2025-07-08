import re

# patterns of amrex/quokka output
RE_ZONE_UPDATE_RATE = re.compile(r'(\d+\.?\d*)\s+μs/zone-update\s+\[(\d+\.?\d*)\s+Mupdates/s\]')

RE_N_MPI_PROCESS = re.compile(r'MPI initialized with (\d+) MPI processes') 

ELPASE_TIME = re.compile(r'elapsed time:\s*(.*?)\s*seconds\.')


# HPC specific patterns

# Ngarrgu Tindebeek HPC
# RE_NT_JOB_STATUS = re.compile(r'Job Report: \d+ \(([^)]+)\)')