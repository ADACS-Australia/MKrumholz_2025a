from importlib import metadata  # make sure to import metadata explicitly

__version__ = metadata.version(__package__ or __name__)

from hpc_performance_testing.main import submit_jobs
