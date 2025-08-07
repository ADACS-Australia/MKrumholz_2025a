import yaml
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Literal

from hpc_performance_testing.utils import validate_path, backup_existing_file, get_lowercase_str
from hpc_performance_testing.types import MemSize
from hpc_performance_testing.logger import LoggerManager

# get logger
logger = LoggerManager.get_logger()

KNOWN_CLUSTERS = {
    "nt": {"scheduler": "slurm", "gpu_build": "cuda"},
    "setonix": {"scheduler": "slurm", "gpu_build": "hip"},
    "frontier": {"scheduler": "slurm", "gpu_build": "hip"},
    "gadi": {"scheduler": "pbs", "gpu_build": "cuda"},
}

class HPCConfig(BaseModel):
    cluster: str
    scheduler: Literal["slurm", "pbs"]
    gpu_build: Literal["cuda", "hip"]

    @field_validator("cluster", "scheduler", "gpu_build", mode="before")
    @classmethod
    def lowercase_before_literal(cls, v):
        return get_lowercase_str(v)
    
    def model_post_init(self, __context):
        if self.cluster in KNOWN_CLUSTERS:
            known = KNOWN_CLUSTERS[self.cluster]
            if self.scheduler != known["scheduler"]:
                logger.warning(
                    f"[HPCConfig] Cluster '{self.cluster}' typically uses scheduler '{known['scheduler']}', "
                    f"but '{self.scheduler}' was provided."
                )
            if self.gpu_build != known["gpu_build"]:
                logger.warning(
                    f"[HPCConfig] Cluster '{self.cluster}' typically uses GPU build '{known['gpu_build']}', "
                    f"but '{self.gpu_build}' was provided."
                )
        else:
            logger.warning(
                f"[HPCConfig] Cluster '{self.cluster}' is not in the list of known clusters. "
                f"A generic template will be used, which may not work correctly on this system."
            )
    model_config = ConfigDict(
        extra="forbid",
    )

class PathsConfig(BaseModel):
    working_dir: str
    environment: str
    test_inputs: str

    @field_validator("working_dir", "environment", "test_inputs", mode="after")
    @classmethod
    def validate_paths(cls, v):
        return validate_path(v)

    model_config = ConfigDict(
        extra="forbid"
    )

class JobSettings(BaseModel):
    shell: Optional[str] = None
    ntasks_per_node: Optional[int] = None
    cpus_per_task: Optional[int] = None
    walltime: Optional[str] = None
    mem_per_cpu: Optional[MemSize] = None
    mem_per_node: Optional[MemSize] = None
    jobfs_per_node: Optional[MemSize] = None
    partition: Optional[str] = None
    account: Optional[str] = None

    @field_validator("mem_per_cpu", "mem_per_node", "jobfs_per_node", mode="before")
    @classmethod
    def convert_to_memsize(cls, v):
        if v is None:
            return v
        return v if isinstance(v, MemSize) else MemSize(v)
    
    model_config = ConfigDict(
        extra="allow", # allow custom job options
        arbitrary_types_allowed=True
    )


class ScalingConfig(BaseModel):
    strategy: Literal["weak_3d"]
    min_cores: Optional[int] = None
    max_cores: int

    @field_validator("strategy", mode="before")
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

class TestItem(BaseModel):
    name: str
    target: str
    input_file: str
    cmake_cache: Optional[List[str]] = Field(default_factory=list)
    job_settings: Optional[JobSettings] = Field(default=None)

    model_config = ConfigDict(
        extra="forbid"  # allow flexible test configs
    )

class FullConfig(BaseModel):
    hpc: HPCConfig
    paths: PathsConfig
    global_job_settings: JobSettings
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
    
    @model_validator(mode="after")
    def validate_job_settings(self):
        global_settings = self.global_job_settings

        required_fields = ['walltime', 'shell', 'ntasks_per_node']

        for field in required_fields:
            global_value = getattr(global_settings, field, None)

            for test in self.tests:
                test_value = getattr(test.job_settings, field, None) if test.job_settings else None

                if global_value is None and test_value is None:
                    raise ValueError(
                        f"Test '{test.name}' is missing '{field}' and no global '{field}' is defined."
                    )

        return self
    

    
    model_config = ConfigDict(
        extra="forbid"  # forbid unknown top-level keys
    )


def convert_non_str_to_str(obj):
    _CONVERTIBLE_TYPES = (Path, MemSize)
    if isinstance(obj, dict):
        return {k: convert_non_str_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_non_str_to_str(v) for v in obj]
    elif isinstance(obj, _CONVERTIBLE_TYPES):
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
    clean_config = convert_non_str_to_str(config_cpy)
    
    # Write new metadata
    with metadata_path.open("w") as f:
        yaml.safe_dump(clean_config, f, default_flow_style=False, sort_keys=False)

    logger.info(f"run_metadata.yaml written to {metadata_path}")