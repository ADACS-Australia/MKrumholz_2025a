import os
import pandas as pd

Job_FIELD = {
            "job_id": str,
            "test_name": str,    
            "test_folder": str,        
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
    
    required_field = "job_id"
    
    def __init__(self, fields: list[str] | dict| None = None):
        if fields is None:
            self.df = pd.DataFrame()
        else:
            self.fields = self._validate_fields(fields)
            self.df = pd.DataFrame(columns=fields)

    @classmethod
    def from_df(cls, df: pd.DataFrame, fields: list[str] | dict | None = None):   
        # check no duplicated columns
        if not df.columns.is_unique:
            dup_cols = [c for c in df.columns if (df.columns == c).sum() > 1]
            raise ValueError(f"Duplicate column names in DataFrame: {sorted(set(dup_cols))}")
        
        _fields = list(df.columns)
        
        if fields is None:
            fields = _fields
        fields = cls._validate_fields(fields)
        
        if set(_fields) != set(fields):
            raise ValueError(f"The provided fields {fields} don't match with dataframe columns {_fields}")
        
        self = cls.__new__(cls)
        self.fields = fields
        self.df = df

        return self 
       
    @classmethod
    def _validate_fields(cls, fields):
        if isinstance(fields, dict):
            fields = list(fields.keys())
        
        if not isinstance(fields, list):
            raise TypeError(f"Field names must be of type list[str] or dict; {fields} is of type {type(fields)}")
        
        if not all(isinstance(name, str) for name in fields):
            bad = [type(name).__name__ for name in fields if not isinstance(name, str)]
            raise TypeError(f"All field names must be strings; got invalid types: {bad}")
        
        # check duplicates
        if len(fields) != len(set(fields)):
            seen = set()
            dups = [f for f in fields if f in seen or seen.add(f)]
            raise ValueError(f"Duplicate field names are not allowed: {dups}")
        
        # job_id must be one of the field names
        if cls.required_field not in fields:
            raise ValueError("'job_id' must be included in fields!")
        
        return fields
    
    @property
    def job_list(self) -> list:
        if "job_id" in self.df.columns:
            return self.df["job_id"].astype(str).tolist()
        else:
            return []
        
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
