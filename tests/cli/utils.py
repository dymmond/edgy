import os
import shlex
import subprocess


def run_cmd(app, cmd, is_app=True):
    env = dict(os.environ)
    if is_app:
        env["EDGY_DEFAULT_APP"] = app
    cmd = f"hatch --env test run {cmd}"

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=True)
    print("\n$ " + cmd)
    print(result.stdout.decode("utf-8"))
    print(result.stderr.decode("utf-8"))
    return result.stdout, result.stderr, result.returncode
