from enum import Enum
from pathlib import Path
import shutil

from hpc_performance_testing.config import load_yaml
from hpc_performance_testing.utils import validate_path, backup_existing_file
from hpc_performance_testing.logger import LoggerManager

# get logger
logger = LoggerManager.get_logger()

class CleanupScenario(str, Enum):
    RESUBMIT   = "resubmit"
    FINISHED   = "finished"
    DELETE_ALL = "delete_all"

class TestInstanceCleanup:

    TEST_YAML_NAME = "test_instance.yaml"
    ERR_LOG_NAME   = "runtime_err.log"
    
    def __init__(self):
        self.test_instance_path = self._get_test_instance_path()

    def _get_test_instance_path(self):
        test_yaml_path = Path(self.TEST_YAML_NAME)
        if not test_yaml_path.exists():
            return None
       
        try:
            cfg = load_yaml(test_yaml_path)
        except Exception:
            return None
        
        raw = cfg.get("runtime", {}).get("test_instance")
        if not raw:
            return None

        # Validate & normalize path; return None if invalid
        try:
            return validate_path(raw)
        except Exception:
            return None

    def _move_to(self) -> list[str]:
        
        moved = []
        names = (self.TEST_YAML_NAME, self.ERR_LOG_NAME)
        sources = list(map(Path, names))    
        dst = self.test_instance_path

        if dst is None:
            for src in sources:
                src.unlink(missing_ok=True)
                logger.info(f"Test Instance is not found. Delete file {src.name} if exists.")
            return moved
        
        for src in sources:
            if not src.exists():
                continue

            dst_file = dst/src.name
            if dst_file.exists():
                backup_existing_file(dst_file)
            shutil.move(str(src), str(dst))
            logger.info(f"Move file {src.name} to {str(dst)}")
            moved.append(src.name)

        return moved
            

if __name__ == "__main__":
    cleanup = TestInstanceCleanup()
    cleanup._move_to()