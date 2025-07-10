#!/bin/bash
# remove all pycache dirs
find . -name "__pycache__" -print0 | xargs -0 rm -rf
