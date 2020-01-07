import shutil
import subprocess
import sys
import time

"""
Benchmark Checkbox with different scenarios.

This program runs a particular launcher and measures how long it took to run it.
Place this file and the 2019.com.canonical.certification:metabench provider in the checkbox-ng tree and run it.
"""


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: {} SCENARIO".format(sys.argv[0]))

    shutil.rmtree('venv', ignore_errors=True)
    subprocess.run("./mk-venv")
    subprocess.run(". venv/bin/activate; ./2019.com.canonical.certification:metabench/manage.py develop -d $PROVIDERPATH", shell=True)
    launcher = "./2019.com.canonical.certification:metabench/launcher-{}".format(sys.argv[1])

    start = time.time()
    output = subprocess.check_output(". venv/bin/activate; {}".format(launcher), shell=True, stderr=subprocess.STDOUT)
    print(time.time() - start)

if __name__ == '__main__':
    main()

