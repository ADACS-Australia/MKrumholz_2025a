import os
import pandas as pd

Job_FIELD = {
            "test_name": str,
            "job_id": int,
            "n_cell": str,
            "n_cores": int,
            "cores_per_node": int,
            "n_nodes": int,
        }

Result_FIELD = {
        "exit_status": str,
        "microseconds_per_update": float,
        "megaupdates_per_second": float,
        "microseconds_per_update_per_core": float,
        "megaupdates_per_second_per_core": float,

    }

class JobDataFrame:
    
    def __init__(self, fields:dict):
        self.fields = fields
        self.df = pd.DataFrame(columns=fields.keys())
        
    def add_job_entry(self, job_id:int, **kwargs):
        row = {"job_id": job_id}
        for key in self.fields.keys():
            if key != "job_id":
                row[key] = kwargs.get(key, None)
        self.df.loc[len(self.df)] = row

    def save(self, filename:str|os.PathLike):
        self.df.to_parquet(filename, index=False)
    
    def load(self, filename:str):
        return pd.read_parquet(filename)
