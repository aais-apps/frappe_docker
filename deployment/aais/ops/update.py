#!/usr/bin/env python3
"""Fetch the tested image and its matching deployment configuration before release."""
import datetime
import fcntl
import os
import pathlib
import shutil
import subprocess
import tarfile
import tempfile

root = pathlib.Path('/home/nirog/aais-erp')
os.chdir(root)
lock = pathlib.Path('/home/nirog/aais-backups/deploy.lock').open('a')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print('Another deployment is active')
    raise SystemExit(0)
# Python closes this non-inheritable descriptor on exec. deploy.sh then takes
# the same lock; no running deployment can have its scripts overwritten here.


def output(*args):
    return subprocess.check_output(args, text=True).strip()


image = 'ghcr.io/aais-apps/erpnext:production'
subprocess.run(['docker', 'pull', image], check=True)
candidate = output('docker', 'image', 'inspect', image, '--format', '{{index .RepoDigests 0}}')
current = output('docker', 'inspect', 'aais-erp-backend-1', '--format', '{{.Image}}')
next_image = output('docker', 'image', 'inspect', image, '--format', '{{.Id}}')
if current == next_image:
    print('No new tested release')
    raise SystemExit(0)

stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
previous = pathlib.Path('/home/nirog/aais-backups') / ('deployment-code-' + stamp)
previous.mkdir(mode=0o700)
shutil.copy2(root / 'compose.yaml', previous / 'compose.yaml')
with tarfile.open(previous / 'ops.tar.gz', 'w:gz') as archive:
    archive.add(root / 'ops', arcname='ops')
with tempfile.TemporaryDirectory(prefix='aais-deployment-') as temporary:
    container = output('docker', 'create', '--entrypoint', 'true', candidate)
    try:
        subprocess.run(['docker', 'cp', container + ':/opt/aais-deployment/.', temporary], check=True)
    finally:
        subprocess.run(['docker', 'rm', '-v', container], check=True, stdout=subprocess.DEVNULL)
    source = pathlib.Path(temporary)
    subprocess.run(['docker', 'compose', '--env-file', str(root / '.env'), '-f', str(source / 'compose.yaml'), 'config', '--quiet'], check=True)
    shutil.copytree(source / 'ops', root / 'ops', dirs_exist_ok=True)
    shutil.copy2(source / 'compose.yaml', root / 'compose.yaml')
for script in (root / 'ops').glob('*.sh'):
    script.chmod(0o750)
os.environ['AAIS_PREVIOUS_COMPOSE'] = str(previous / 'compose.yaml')
os.execv(str(root / 'ops/deploy.sh'), [str(root / 'ops/deploy.sh'), candidate])
