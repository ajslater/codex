#!/bin/bash
# remove all pycache dirs
find codex -name "__pycache__" -print0 | xargs -0 rm -rf
