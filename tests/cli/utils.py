import asyncio
import os
import subprocess
import sys
from os.path import dirname

from tests.settings import TEST_DATABASE


def run_cmd(app, cmd, with_app_environment=True, extra_env=None):
    env = dict(os.environ)
    # for main.py
    env["TEST_DATABASE"] = TEST_DATABASE
    env["PATH"] = f"{dirname(sys.executable)}:{env['PATH']}"
    env.setdefault("PYTHONPATH", env["PWD"])
    if with_app_environment:
        env["EDGY_DEFAULT_APP"] = app
    if extra_env:
        env.update(extra_env)

    result = subprocess.run(cmd, capture_output=True, env=env, shell=True)
    print("\n$ " + cmd)
    print(result.stdout.decode("utf-8"))
    print(result.stderr.decode("utf-8"))
    return result.stdout, result.stderr, result.returncode


async def arun_cmd(app, cmd, with_app_environment=True, extra_env=None):
    env = dict(os.environ)
    # for main.py
    env["TEST_DATABASE"] = TEST_DATABASE
    env["PATH"] = f"{dirname(sys.executable)}:{env['PATH']}"
    env.setdefault("PYTHONPATH", env["PWD"])
    if with_app_environment:
        env["EDGY_DEFAULT_APP"] = app
    if extra_env:
        env.update(extra_env)

    process = await asyncio.create_subprocess_shell(
        cmd, env=env, stderr=subprocess.PIPE, stdout=subprocess.PIPE
    )
    print("\n$ " + cmd)
    stdout, stderr = await process.communicate()
    print(stdout.decode("utf-8"))
    print(stderr.decode("utf-8"))
    return stdout, stderr, process.returncode
