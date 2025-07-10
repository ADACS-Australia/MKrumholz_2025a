import os
from pathlib import Path
import stat
import uuid
from importlib.resources import files
import shutil

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

def backup_existing_file(file_path : Path | str) -> Path:
    file_path = validate_path(file_path)
    filename = file_path.name
    unique_id = uuid.uuid4().hex[:8]
    backup_file = file_path.with_name(f"{filename}.old.{unique_id}")

    shutil.move(str(file_path), str(backup_file))
    return backup_file

def flatten_dict(d: dict, parent_key: str = "", sep: str = "_") -> dict:
    items = []
    assert isinstance(d, dict), f"{d} must be a dict"
    
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)