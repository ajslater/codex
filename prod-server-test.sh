#!/bin/sh
bash -c "cd frontend && npm run build"
./collectstatic.sh
./run.sh
