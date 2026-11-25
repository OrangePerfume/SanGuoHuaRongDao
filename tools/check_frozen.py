"""Run the packaged Windows EXE with a bounded, offscreen startup check."""
import os
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    exe = Path(sys.argv[1]).resolve(strict=True)
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    subprocess.run([str(exe), '--smoke-test'], env=env, check=True, timeout=120)
    print('Frozen executable smoke test passed.')
