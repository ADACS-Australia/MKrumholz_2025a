import yaml
from pathlib import Path
from copy import deepcopy
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Optional, List, Literal

from hpc_performance_testing.utils import validate_path, backup_existing_file, get_lowercase_str

class HPCConfig(BaseModel):
    cluster: Literal["nt", "setonix", "frontier", "gadi"]
    scheduler: Literal["slurm", "pbs"]
    shell: str
    env_setup_script: str
    gpu_build: Literal["cuda", "hip"]
    ntasks_per_node: int
    ncpus_per_task: Optional[int] = None
    partition: Optional[str] = None

    @field_validator("cluster", "scheduler", "gpu_build", mode="before")
    @classmethod
    def lowercase_before_literal(cls, v):
        return get_lowercase_str(v)

    @field_validator("env_setup_script", mode="after")
    @classmethod
    def validate_env_script(cls, v):
        return validate_path(v)
    
    model_config = ConfigDict(
        extra="allow"
    )

class PathsConfig(BaseModel):
    working_dir: str
    test_inputs: str

    @field_validator("working_dir", "test_inputs", mode="after")
    @classmethod
    def validate_paths(cls, v):
        return validate_path(v)

    model_config = ConfigDict(
        extra="forbid"
    )

class ScalingConfig(BaseModel):
    strategy: Literal["weak_3d"]
    min_cores: Optional[int] = None
    max_cores: int

    field_validator("strategy", mode="before")
    @classmethod
    def lowercase_before_literal(cls, v):
        return get_lowercase_str(v)
    
    @field_validator("min_cores", mode="after")
    @classmethod
    def default_min_cores(cls, v):
        return 1 if v is None else v
    
    model_config = ConfigDict(
        extra="forbid"
    )

class JobSettings(BaseModel):
    time_limit: Optional[str]
    memory: Optional[str]

    model_config = ConfigDict(
        extra="allow"  # allow custom test options
    )

class TestItem(BaseModel):
    name: str
    target: str
    input_file: str
    cmake_cache: Optional[List[str]] 
    job_settings: Optional[JobSettings]

    model_config = ConfigDict(
        extra="forbid"  # allow flexible test configs
    )

class FullConfig(BaseModel):
    hpc: HPCConfig
    paths: PathsConfig
    scaling: ScalingConfig
    tests: List[TestItem]

    @model_validator(mode="after")
    def validate_input_paths(self):
        test_inputs = self.paths.test_inputs
        for test in self.tests:
            full_path = test_inputs / test.input_file
            if not full_path.exists():
                raise FileNotFoundError(
                    f"Input file '{test.input_file}' not found in: {test_inputs}"
                )
        return self
    
    model_config = ConfigDict(
        extra="forbid"  # forbid unknown top-level keys
    )


def convert_paths_to_str(obj):
    if isinstance(obj, dict):
        return {k: convert_paths_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_paths_to_str(v) for v in obj]
    elif isinstance(obj, Path):
        return str(obj)
    else:
        return obj

# Load config
def load_config(file="config.yaml"):
    with open(file) as f:
        raw_config = yaml.safe_load(f)
    config = FullConfig(**raw_config)
   
    return config


def write_test_instance_meta(config: FullConfig, test_instance_path: Path | str, out_dir: Path = None):
    config_cpy = config.model_dump()
    test_instance_path = validate_path(test_instance_path)

    if out_dir is None:
        out_dir = Path.cwd()
    out_dir = validate_path(Path(out_dir))
    

    metadata_path = out_dir / "test_instance.yaml"

    # Backup old file if exists
    if metadata_path.exists():
        backup_existing_file(metadata_path)

    # Merge with runtime metadata
    config_cpy["runtime"] = {
        "timestamp": test_instance_path.name ,
        "test_instance": str(test_instance_path),
         
    }

    # Convert Path objects to str
    clean_config = convert_paths_to_str(config_cpy)
    # Write new metadata
    with metadata_path.open("w") as f:
        yaml.safe_dump(clean_config, f, default_flow_style=False, sort_keys=False)

    print(f"[INFO] run_metadata.yaml written to {metadata_path}")