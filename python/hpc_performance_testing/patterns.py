import re

# pattern of job output file
JOB_OUTPUT_NAME = re.compile(r"_JobID_(?P<job_id>[a-zA-Z0-9_\-]+)\.out$")

# patterns of amrex/quokka output
ZONE_UPDATE_RATE = re.compile(r'(\d+\.?\d*)\s+μs/zone-update\s+\[(\d+\.?\d*)\s+Mupdates/s\]')

N_MPI_PROCESS = re.compile(r'MPI initialized with (\d+) MPI processes') 

ELPASE_TIME = re.compile(r'elapsed time:\s*(.*?)\s*seconds\.')

# table patterns
_TABLE_REGEX_TEMPLATE = r"-+\n({header_pattern})\n-+\n(.*?)(?=\n-+)"
_TIMING_TEMPLATE = r"Name\s+NCalls\s+{label_prefix}\. Min\s+{label_prefix}\. Avg\s+{label_prefix}\. Max\s+Max %"
TIMING_INCLUSIVE = re.compile(_TABLE_REGEX_TEMPLATE.format(header_pattern = _TIMING_TEMPLATE.format(label_prefix = "Incl")), flags=re.DOTALL)
TIMING_EXCLUSIVE = re.compile(_TABLE_REGEX_TEMPLATE.format(header_pattern = _TIMING_TEMPLATE.format(label_prefix = "Excl")), flags=re.DOTALL)
# TIMING_INCLUSIVE = r"Name\s+NCalls\s+Incl\. Min\s+Incl\. Avg\s+Incl\. Max\s+Max %"
# TIMING_EXCLUSIVE = r"Name\s+NCalls\s+Excl\. Min\s+Excl\. Avg\s+Excl\. Max\s+Max %"


# HPC specific patterns

# Ngarrgu Tindebeek HPC
# RE_NT_JOB_STATUS = re.compile(r'Job Report: \d+ \(([^)]+)\)')