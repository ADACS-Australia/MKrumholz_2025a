import yaml

from hpc_performance_testing.util import resolve_path

#todo: add function to check config fields

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

    if not env_script.exists():
        raise FileNotFoundError(f"Environment script {env_script} is not found.")

    return config