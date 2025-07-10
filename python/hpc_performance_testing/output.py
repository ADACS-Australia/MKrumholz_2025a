import os
import pandas as pd

Job_FIELD = {
            "test_name": str,
            "job_id": str,
            "n_cell": str,
            "n_cores": int,
            "cores_per_node": int,
            "n_nodes": int,
        }

Job_output_FIELD = {
        "job_id": str,
        "n_mpi_processes": int,
        "zone_update": dict,
        "elapse_time": float,
        "boundary_condition_inc_main": dict
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
