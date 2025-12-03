import json
import os
import platform
import time

def save_asv_history(suite, test_list):
    """
    Save test results in Airspeed Velocity (ASV) format.
    """
    
    # Get the commit hash from the source repo
    commit_hash = "unknown"
    if suite.sourceTree in suite.repos:
        if suite.repos[suite.sourceTree].hash_current:
             commit_hash = suite.repos[suite.sourceTree].hash_current.strip()
    
    if commit_hash == "unknown":
        # Fallback: use the first repo or "source"
        if "source" in suite.repos and suite.repos["source"].hash_current:
            commit_hash = suite.repos["source"].hash_current.strip()
        elif len(suite.repos) > 0:
            # Use the first available repo hash
            first_repo = list(suite.repos.values())[0]
            if first_repo.hash_current:
                commit_hash = first_repo.hash_current.strip()

    # Current timestamp in milliseconds
    timestamp = int(time.time() * 1000)

    # Environment and Machine Info
    machine_name = platform.node()
    os_name = platform.system()
    python_version = platform.python_version()

    params = {
        "machine": machine_name,
        "os": os_name,
        "python": python_version
    }

    results = {}
    for test in test_list:
        # We only care about tests that passed execution and have a wall time
        # Use record_runtime logic but we can be slightly more permissive if needed,
        # but keeping it consistent with wallclock_history is good.
        if test.record_runtime(suite):
             results[test.name] = test.wall_time

    if not results:
        return

    data = {
        "version": 1,
        "commit_hash": commit_hash,
        "env_name": f"regtest-{machine_name}",
        "date": timestamp,
        "params": params,
        "results": results,
        "requirements": {} 
    }

    # Determine output path
    # We'll put it in a 'asv' subdirectory within the benchmarks directory
    try:
        bench_dir = suite.get_bench_dir()
    except SystemExit:
        # If get_bench_dir fails (e.g. dir doesn't exist and strict checking), 
        # we might skip ASV saving or try to create it if allowed.
        # But regtest.py usually ensures bench_dir is checked.
        return

    asv_dir = os.path.join(bench_dir, "asv")
    machine_dir = os.path.join(asv_dir, machine_name)

    if not os.path.exists(machine_dir):
        try:
            os.makedirs(machine_dir)
        except OSError:
            suite.log.warn(f"Could not create ASV directory: {machine_dir}")
            return

    output_file = os.path.join(machine_dir, f"{commit_hash}.json")

    try:
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=4)
        suite.log.log(f"ASV results saved to {output_file}")
    except Exception as e:
        suite.log.warn(f"Failed to save ASV results: {e}")
