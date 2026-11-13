#!/usr/bin/env bash
set -Eeuo pipefail
# Caddy reaches these services locally. Public applications and SSH retain access.
for port in 8085 9000 9443; do
  rule=(-i eth0 -p tcp -m conntrack --ctorigdstport "$port" -j DROP)
  iptables -C DOCKER-USER "${rule[@]}" 2>/dev/null || iptables -I DOCKER-USER 1 "${rule[@]}"
  rule6=(-i eth0 -p tcp --dport "$port" -j DROP)
  ip6tables -C INPUT "${rule6[@]}" 2>/dev/null || ip6tables -I INPUT 1 "${rule6[@]}"
done
