#!/usr/bin/env python3
"""Record service and backup health without exposing a public monitoring endpoint."""
import datetime
import fcntl
import json
import pathlib
import subprocess
import time
import urllib.request

root = pathlib.Path('/home/nirog/aais-backups')
with (root / 'deploy.lock').open('a') as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        print('Deployment in progress; skipping transient health checks')
        raise SystemExit(0)
    errors = []
    for service in ['backend', 'frontend', 'scheduler', 'queue-short', 'queue-long', 'websocket', 'db', 'redis-cache', 'redis-queue']:
        result = subprocess.run(['docker', 'inspect', 'aais-erp-' + service + '-1'], capture_output=True, text=True)
        if result.returncode:
            errors.append(service + ': missing')
            continue
        state = json.loads(result.stdout)[0]['State']
        if not state['Running'] or state.get('OOMKilled') or state.get('Health', {}).get('Status') == 'unhealthy':
            errors.append(service + ': unhealthy')
    try:
        request = urllib.request.Request('http://127.0.0.1:8085/api/method/ping', headers={'Host': 'erp.paradox-bd.com'})
        with urllib.request.urlopen(request, timeout=10) as response:
            assert json.load(response)['message'] == 'pong'
    except Exception:
        errors.append('API health check failed')
    backup = root / 'last-success'
    if not backup.exists() or time.time() - backup.stat().st_mtime > 36 * 3600:
        errors.append('No verified backup in the last 36 hours')
    report = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'healthy': not errors, 'errors': errors}
    (root / 'health.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    raise SystemExit(bool(errors))
