import os
from pathlib import Path
import stat

def resolve_path(path: str):
    # resolve environment variable and ~
    expanded = os.path.expanduser(os.path.expandvars(path))
    return Path(expanded).resolve()


def make_executable(file:str) -> None:
    """change the file to executable"""
    os.chmod(file, os.stat(file).st_mode | stat.S_IXUSR)
