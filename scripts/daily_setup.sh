#!/usr/bin/env bash
# تجهيز جهاز جديد لجولة البحث اليومية: Docker + صورة الـ sandbox + استرجاع ذاكرة المدينة من city_state/.
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -q -r requirements.txt yfinance 2>/dev/null || pip install -q -r requirements.txt yfinance
if ! docker info >/dev/null 2>&1; then
  (dockerd >/tmp/dockerd.log 2>&1 &)
  for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
fi
docker image inspect agentcity-sandbox:1 >/dev/null 2>&1 || python agentcity.py sandbox | tail -1
python agentcity.py state import
python agentcity.py lab daily | head -3
