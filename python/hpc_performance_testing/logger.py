import logging
import warnings
from pathlib import Path
import sys
import traceback
import uuid

class LoggerManager:
    _logger = None
    _log_err_file = None
    _log_pipeline_file = None

    @classmethod
    def init(cls, log_dir: Path | str = None, name: str = "perf_test"):
        # get logger
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG) # handlers decide the level 
        logger.handlers.clear()

        # err log
        if log_dir is None:
            log_dir = Path.cwd()    
        log_dir = Path(str(log_dir))
        
        if not log_dir.exists():
            msg = f"Directory {log_dir} doesn't exist! Log in to the current directory instead."
            warnings.warn(msg)
            log_dir = Path.cwd()
        
        cls._log_err_file = log_dir/"runtime_err.log"
               
        err_fh = logging.FileHandler(cls._log_err_file, mode='a')
        err_fh.setLevel(logging.ERROR)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        err_fh.setFormatter(formatter)
        logger.addHandler(err_fh)

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
    def add_pipeline_log(cls, test_instance: Path):
        if not Path(test_instance).exists():
            raise FileNotFoundError(f"Test instance {test_instance} doesn't exists!")
        pipline_log = test_instance/"perf_test.log"
        pipeline_fh = logging.FileHandler(pipline_log, mode='a')
        pipeline_fh.setLevel(logging.INFO)
        pipeline_fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        if cls._logger is None:
            raise  RuntimeError("LoggerManager not initialized. Call LoggerManager.init(log_dir) first.")
        
        cls._logger.addHandler(pipeline_fh)
        cls._log_pipeline_file = pipline_log


    @classmethod
    def get_logger(cls):
        if cls._logger is None:
            raise RuntimeError("LoggerManager not initialized. Call LoggerManager.init(log_dir) first.")
        return cls._logger

    @classmethod
    def get_log_file(cls):
        return cls._log_file
