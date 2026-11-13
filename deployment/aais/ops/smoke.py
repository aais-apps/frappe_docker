#!/usr/bin/env python3
"""Check every published page, login and API health through the local reverse proxy."""
import json
import subprocess
import urllib.error
import urllib.request

result = subprocess.check_output([
    "docker", "exec", "aais-erp-backend-1", "bench", "--site", "erp.aais.local",
    "execute", "frappe.get_all", "--kwargs",
    json.dumps({"doctype": "Builder Page", "filters": {"published": 1}, "pluck": "route"}),
], text=True)
routes = json.loads(result.strip().splitlines()[-1])
for path in ["/api/method/ping", "/login", "/edu-portal", *["/" + route for route in routes]]:
    request = urllib.request.Request("http://127.0.0.1:8085" + path, headers={"Host": "erp.paradox-bd.com"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
        assert response.status == 200, (path, response.status)
        if path == "/api/method/ping":
            assert json.loads(body)["message"] == "pong"
print(f"PASS: API, login, portal and {len(routes)} published pages")
