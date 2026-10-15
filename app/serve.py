"""Run the NCET VerifyFlow API and worker in a single container.

A single-service option for low-traffic pilots. Institutional deployments
should use separate always-on worker services and approved malware scanning.
"""
from __future__ import annotations
import logging
import os
import signal
import subprocess
import sys
import time

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
log = logging.getLogger('ncet.serve')


def main() -> int:
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], check=True)
    subprocess.run([sys.executable, '-m', 'app.bootstrap'], check=True)
    run_worker = os.getenv('APP_RUN_WORKER_IN_WEB', 'false').strip().lower() == 'true'
    port = int(os.getenv('PORT', '10000'))
    programs = [['uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', str(port), '--proxy-headers']]
    if run_worker:
        programs.append([sys.executable, '-m', 'app.worker'])
    children: list[subprocess.Popen] = []
    interrupted = False

    def terminate_children(*_):
        nonlocal interrupted
        interrupted = True
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, terminate_children)
    signal.signal(signal.SIGINT, terminate_children)
    try:
        for command in programs:
            child = subprocess.Popen(command)
            children.append(child)
            log.info('Started %s (pid %s)', command[0], child.pid)
        while not interrupted:
            for child in children:
                code = child.poll()
                if code is not None:
                    log.error('Required process %s exited (code %s)', child.pid, code)
                    terminate_children()
                    return code if code else 1
            time.sleep(1)
    finally:
        terminate_children()
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
