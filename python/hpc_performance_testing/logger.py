import logging
from pathlib import Path

class LoggerManager:
    _logger = None
    _log_file = None

    @classmethod
    def init(cls, log_dir: Path, name: str = "perf_test"):
        cls._log_file = log_dir/"run.log"
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(cls._log_file, mode='a')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        cls._logger = logger

    @classmethod
    def get_logger(cls):
        if cls._logger is None:
            raise RuntimeError("LoggerManager not initialized. Call LoggerManager.init(log_dir) first.")
        return cls._logger

    @classmethod
    def get_log_file(cls):
        return cls._log_file
