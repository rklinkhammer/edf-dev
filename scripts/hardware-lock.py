#!/usr/bin/env python3
"""Hold a repository lock across the entire launcher process tree."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
root = Path(__file__).resolve().parents[1]
mode = fcntl.LOCK_EX if sys.argv[2:3] in (['hardware'], ['build']) else fcntl.LOCK_SH
with (root/'.edf-hardware.lock').open('a') as lock:
    try:
        fcntl.flock(lock, mode | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit('Hardware import/build conflicts with an active EDF command. Wait for it to finish.')
    env = {**os.environ, 'EDF_HARDWARE_LOCKED': '1'}
    # The parent retains ownership; descendants inherit it if the parent is interrupted.
    sys.exit(subprocess.call(['bash', *sys.argv[1:]], env=env, pass_fds=(lock.fileno(),)))
