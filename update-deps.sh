#!/bin/bash
set -euo pipefail
poetry update
poetry show --outdated
npm update
npm outdated
cd frontend
npm update
npm outdated
