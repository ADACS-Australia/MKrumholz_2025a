import os
import pandas as pd

Job_FIELD = {
             "job_id": str,
            "test_name": str,            
            "n_cell": str,
            "n_gpu": int,
            "gpus_per_node": int,
            "n_nodes": int,
        }

Job_output_FIELD = {
        "job_id": str,
        "n_mpi_processes": int,
        "zone_update": dict,
        "elapse_time": float,
        "boundary_condition_inc_main": dict,
    }

Job_status_FIELD = {
    "job_id": str,
    "state": str,
    "exit_code": str,
}

class JobDataFrame:
    
    def __init__(self, fields: list[str] | dict| None = None):
        if fields is None:
            self.df = pd.DataFrame()
        else:
            self.fields = self._validate_fields(fields)
            self.df = pd.DataFrame(columns=fields)

    def _validate_fields(self, fields):
        if isinstance(fields, dict):
            fields = list(fields.keys())
        
        if not isinstance(fields, list):
            raise TypeError(f"Field names must be of type list[str] or dict; {fields} is of type {type(fields)}")
        
        if not all(isinstance(name, str) for name in fields):
            bad = [type(name).__name__ for name in fields if not isinstance(name, str)]
            raise TypeError(f"All field names must be strings; got invalid types: {bad}")
        
        # job_id must be one of the field names
        if "job_id" not in fields:
            raise ValueError("'job_id' must be included in fields!")
        
        return fields
        
    def add_job_entry(self, **kwargs):
        if hasattr(self, "fields"):
            row = {}
            for name in self.fields:
                row[name] = kwargs.get(name, None)
            self.df.loc[len(self.df)] = kwargs
        else:
            self.df = pd.concat([self.df, pd.DataFrame([kwargs])], ignore_index=True)

    def save(self, filename:str|os.PathLike):
        self.df.to_parquet(filename, index=False)
    
    def load(self, filename:str):
        return pd.read_parquet(filename)
