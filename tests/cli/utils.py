import os
import shlex
import subprocess


def run_cmd(app, cmd, is_app=True):
    if is_app:
        os.environ["SAFFIER_DEFAULT_APP"] = app
    process = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = process.communicate()
    print("\n$ " + cmd)
    print(stdout.decode("utf-8"))
    print(stderr.decode("utf-8"))
    return stdout, stderr, process.wait()
