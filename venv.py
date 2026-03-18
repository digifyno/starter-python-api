# venv.py - Shim to work around missing python3.12-venv system package
#
# The build command `python3 -m venv venv` fails when the python3.12-venv
# package is not installed (ensurepip unavailable). This shim intercepts
# `python3 -m venv` (Python searches cwd first) and delegates to the
# `virtualenv` pip package, which works without the system package.
#
# This file can be removed once python3.12-venv is installed server-wide
# via: sudo apt-get install -y python3.12-venv

import sys
import subprocess

if __name__ == "__main__":
    result = subprocess.run(
        [sys.executable, "-m", "virtualenv"] + sys.argv[1:],
        check=False
    )
    sys.exit(result.returncode)
