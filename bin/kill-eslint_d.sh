#!/usr/bin/env bash
# eslint_d can get into a bad state if git switches branches underneath it
npx eslint_d stop
pkill eslint_d
rm -f .eslintcache
