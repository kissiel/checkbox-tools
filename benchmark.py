#!/usr/bin/env python3
# Copyright 2020 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
import glob
import os
import signal
import shutil
import subprocess
import sys
import time

from pprint import pprint

"""
Benchmark Checkbox with different scenarios.

This program runs a particular launcher and measures how long it took to run
it.  Place this file and the benchmarking-provider provider in the checkbox-ng
tree and run it.
"""

def prepare_venv():
    shutil.rmtree('venv', ignore_errors=True)
    subprocess.run(
        "./mk-venv", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(
            (". venv/bin/activate; benchmarking-provider/manage.py"
            "develop -d $PROVIDERPATH"),
            shell=True, stdout=subprocess.DEVNULL)

def run_via_remote(scenario):
    # start the slave
    try:
        slave_proc = subprocess.Popen(
            '. venv/bin/activate; checkbox-cli slave',
            shell=True, start_new_session=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Failed to run the slave")
    launcher = "benchmarking-provider/launcher-{}".format(scenario)
    with contextlib.ExitStack() as stack:
        def kill_slave(*args):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(os.getpgid(slave_proc.pid), signal.SIGTERM)
        stack.push(kill_slave)
        try:
            start = time.time()
            subprocess.run(
                ". venv/bin/activate; checkbox-cli master localhost {}".format(
                    launcher), shell=True, stderr=subprocess.STDOUT)
            stop = time.time()
        except subprocess.CalledProcessError as exc:
            print(exc.stdout.decode(sys.stdout.encoding))
            raise SystemExit("Failed to remotely run scenario {}".format(
                scenario))
        if slave_proc.poll() is not None:
            raise SystemExit("Slave died by its own. Benchmarking failed")
    return stop - start

def run_locally(scenario):
    launcher = "benchmarking-provider/launcher-{}".format(scenario)
    try:
        start = time.time()
        subprocess.run(". venv/bin/activate; checkbox-cli {}".format(
            launcher), shell=True, stderr=subprocess.STDOUT)
        stop = time.time()
    except subprocess.CalledProcessError as exc:
        print(exc.stdout.decode(sys.stdout.encoding))
        raise SystemExit("Failed to remotely run scenario {}".format(scenario))
    return stop - start

def main():
    os.chdir(os.path.split(os.path.abspath(__file__))[0])
    launchers = glob.glob('benchmarking-provider/launcher-*')
    scenarios = [
        s.replace('benchmarking-provider/launcher-', '') for s in launchers]
    results = dict()
    for scenario in scenarios:
        local_result = run_locally(scenario)
        remote_result = run_via_remote(scenario)
        results['local-{}'.format(scenario)] = local_result
        results['remote-{}'.format(scenario)] = remote_result
    pprint(results)
if __name__ == '__main__':
    main()

