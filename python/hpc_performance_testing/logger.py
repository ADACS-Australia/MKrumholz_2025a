import logging
from pathlib import Path
import sys
import traceback

class LoggerManager:
    _logger = None
    _log_file = None

    @classmethod
    def init(cls, log_dir: Path, name: str = "perf_test"):
        cls._log_file = log_dir/"run.log"
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        if not logger.hasHandlers():
            fh = logging.FileHandler(cls._log_file, mode='a')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            logger.addHandler(fh)

            # Console (stdout) handler
            ch = logging.StreamHandler(sys.stdout)  # or sys.stderr if you prefer
            ch.setLevel(logging.INFO)
            console_formatter = logging.Formatter('%(levelname)s - %(message)s')  # simpler output
            ch.setFormatter(console_formatter)
            logger.addHandler(ch)

        cls._logger = logger

        # activate the global exception hook
        cls._setup_global_exception_hook()
        
        return logger

    @classmethod
    def _setup_global_exception_hook(cls):
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                # Let Ctrl+C behave normally
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return         

            # log to logger file if exists
            if cls._logger:
                cls._logger.critical("Uncaught Exception: ", exc_info=(exc_type, exc_value, exc_traceback))
            else:
                # Fallback: print to stderr if logger isn't ready
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                
        sys.excepthook = handle_exception

    @classmethod
    def get_logger(cls):
        if cls._logger is None:
            raise RuntimeError("LoggerManager not initialized. Call LoggerManager.init(log_dir) first.")
        return cls._logger

    @classmethod
    def get_log_file(cls):
        return cls._log_file
