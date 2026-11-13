#!/usr/bin/env python3
import pathlib
import sys

path = pathlib.Path('.env')
lines = [line for line in path.read_text().splitlines() if not line.startswith('ERPNEXT_IMAGE=')]
lines.append('ERPNEXT_IMAGE=' + sys.argv[1])
temporary = path.with_suffix('.tmp')
temporary.write_text('\n'.join(lines) + '\n')
temporary.chmod(0o600)
temporary.replace(path)
