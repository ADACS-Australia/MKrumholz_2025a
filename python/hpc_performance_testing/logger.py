import logging
import warnings
from pathlib import Path
import sys
import traceback
import uuid

class LoggerManager:
    _logger = None
    _log_file = None

    @classmethod
    def init(cls, log_dir: Path | str = None, name: str = "perf_test", existing_log: bool = False):
        if log_dir is None:
            log_dir = Path.cwd()
        elif not isinstance(log_dir, Path):
            log_dir = Path(str(log_dir))
        if not log_dir.exists():
            msg = f"Directory {log_dir} doesn't exist! Log in to the current directory instead."
            warnings.warn(msg)
            log_dir = Path.cwd()
        
        if existing_log:
            _log_file = log_dir/"run.log"
            if not _log_file.exists():
                _log_file = log_dir/cls._add_uuid_name()
                msg = f"Log file run.log doesn't exist in {log_dir}! Create {_log_file.name}."
                warnings.warn(msg)
        else:
            _log_file = log_dir/cls._add_uuid_name()
        cls._log_file = _log_file
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)

        # Clear any existing handlers to avoid duplicates
        logger.handlers.clear()
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
    def _add_uuid_name(cls):
        uu = uuid.uuid4().hex[:8]
        return f"run_{uu}.log"
    
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
