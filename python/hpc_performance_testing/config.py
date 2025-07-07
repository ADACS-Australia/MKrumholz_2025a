import yaml
from pathlib import Path
from copy import deepcopy

from hpc_performance_testing.utils import resolve_path, validate_path, backup_existing_file

#todo: add function to check config fields

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
        config = yaml.safe_load(f)

    # resolve paths
    for key, path_value in config["paths"].items():
        config["paths"][key] = resolve_path(path_value)
   
    # validation
    # check wether env script exists
    env_script = resolve_path(config["env"]["script"])
    config["env"]["script"] = env_script
    if not env_script.exists():
        raise FileNotFoundError(f"Environment script {env_script} is not found.")
    
    # check whether test_inputs directory exists
    test_inputs_dir = config["paths"]["test_inputs"]
    if not test_inputs_dir.exists():
        raise FileNotFoundError(f"Test inputs directory {test_inputs_dir} is not found.")

    return config


def write_test_instance_meta(config: dict, test_instance: Path | str, out_dir: Path = None):
    config_cpy = deepcopy(config)
    test_instance = validate_path(test_instance)

    if out_dir is None:
        out_dir = Path.cwd()
    out_dir = validate_path(Path(out_dir))
    

    metadata_path = out_dir / "test_instance.yaml"

    # Backup old file if exists
    if metadata_path.exists():
        backup_existing_file(metadata_path)

    # Merge with runtime metadata
    config_cpy["runtime"] = {
        "timestamp": test_instance.name ,
        "test_instance": str(test_instance),
         
    }

    # Convert Path objects to str
    clean_config = convert_paths_to_str(config_cpy)
    # Write new metadata
    with metadata_path.open("w") as f:
        yaml.safe_dump(clean_config, f, default_flow_style=False, sort_keys=False)

    print(f"[INFO] run_metadata.yaml written to {metadata_path}")