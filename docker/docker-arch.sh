#!/bin/bash
# get the target arch for the platform
if [[ ${PLATFORMS-} == "linux/armhf" ]]; then
    ARCH=aarch32
else
    ARCH=$(uname -m)
fi
echo "$ARCH"
