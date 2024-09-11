import os
import subprocess


def run_cmd(app, cmd, is_app=True):
    env = dict(os.environ)
    env.setdefault("PYTHONPATH", env["PWD"])
    if is_app:
        env["EDGY_DEFAULT_APP"] = app
    cmd = f"hatch --env test run {cmd}"

    result = subprocess.run(cmd, capture_output=True, env=env, shell=True)
    print("\n$ " + cmd)
    print(result.stdout.decode("utf-8"))
    print(result.stderr.decode("utf-8"))
    return result.stdout, result.stderr, result.returncode
