import os
from pathlib import Path
import stat
from importlib.resources import files

def resolve_path(path: str):
    # resolve environment variable and ~
    expanded = os.path.expanduser(os.path.expandvars(path))
    return Path(expanded).resolve()


def make_executable(file:str) -> None:
    """change the file to executable"""
    os.chmod(file, os.stat(file).st_mode | stat.S_IXUSR)

def load_template(template_name):
    return (files('hpc_performance_testing') / 'templates' / template_name)

def validate_path(path: Path | str) -> Path:
    path = Path(path)
    if not path.exists():
        msg = f"{path} doesn't exist."
        # logger.error(msg)
        raise FileNotFoundError(msg)  
    return path

