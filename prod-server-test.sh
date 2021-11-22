#!/bin/sh
# XXX https://stackoverflow.com/questions/69394632/webpack-build-failing-with-err-ossl-evp-unsupported
bash -c "cd frontend && npm run build"
./collectstatic.sh
./run.sh
