#!/usr/bin/env python3
"""Restore a frozen release snapshot. Called only while all application services are stopped."""
import gzip
import json
import pathlib
import re
import subprocess
import sys

backup = pathlib.Path(sys.argv[1]).resolve()
assert str(backup).startswith("/home/nirog/aais-backups/")
config = json.loads(sorted(backup.glob("*-site_config_backup.json"))[-1].read_text())
name = config["db_name"]
assert re.fullmatch(r"[A-Za-z0-9_]+", name)
dump = sorted(backup.glob("*-database.sql.gz"))[-1]
command = ["docker", "exec", "-i", "aais-erp-db-1", "sh", "-c", 'export MYSQL_PWD="$MARIADB_ROOT_PASSWORD"; exec mariadb -uroot']
subprocess.run(command, input=f"DROP DATABASE `{name}`; CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;".encode(), check=True)
with gzip.open(dump, "rb") as sql:
    subprocess.run(command, input=b"USE `" + name.encode() + b"`;\n" + sql.read(), check=True)
print("Frozen database snapshot restored")
