import sys
import os
from pathlib import Path

from hpc_performance_testing import submit_jobs, check_jobs, extract_results, cleanup
from hpc_performance_testing.utils import validate_path


ALL_ACTIONS = ("submit", "check", "extract", "cleanup")

help_msg = """
Available commands:

hptest submit <config.yml>
hptest check <test_instance.yml>
hptest extract <test_instance.yml>
hptest cleanup [resubmit|finished|delete_all]

Run 'hptest --help' to see this message. 

"""

def print_usage():
    print("Usage: {} <command> <arguments>".format(os.path.basename(sys.argv[0])))
    print(help_msg)

def get_action_and_arg():
    """Pop first argument, check it is a valid action."""
    if len(sys.argv) != 3:
        print_usage()
        sys.exit(1)
    if sys.argv[1] not in ALL_ACTIONS:
        print_usage()
        sys.exit(1)

    return (sys.argv[1], sys.argv[2])

def action_submit(arg: str) -> int:
    """
    submit <config.yml>
      Submit jobs from a YAML config file.
    """
    config_file = validate_path(arg)
    submit_jobs(config_file)
    return 0
    
def action_check(arg: str) -> int:
    """
    check <test_instance.yml>
      Check job statuses; prints WAIT/FINISHED and returns exit code.
      Exit codes: 0 = FINISHED, 3 = WAIT.
    """
    
    test_instance_yaml = validate_path(arg)
    status = check_jobs(test_instance_yaml)
    print(getattr(status, "value", status))
    name = getattr(status, "name", str(status)).upper()
    return 0 if name == "FINISHED" else 3

def action_extract(arg: str) -> int:
    test_instance_yaml = validate_path(arg)
    extract_results(test_instance_yaml)
    return 0

def action_cleanup(arg: str) -> int:
    """
    cleanup [resubmit|finished|delete_all]
      Cleanup test instance files under a chosen scenario (default: resubmit).
    """
    scenario = (arg.lower())
    if scenario not in {"resubmit", "finished", "delete_all"}:
        sys.stderr.write(
            "ERROR: cleanup scenario must be one of "
            "[resubmit|finished|delete_all]\n\n"
        )
    cleanup(scenario)
    return 0

def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--help":
        print_usage()
        return 0
    
    actions = {
        "submit": action_submit,
        "check": action_check,
        "extract": action_extract,
        "cleanup": action_cleanup,
    }
    
    action, arg = get_action_and_arg()
    
    actions[action](arg)
    
    

   
    
if __name__ == "__main__":
    main()