#!/bin/bash
# eslint_d can get into a bad state if git switches branches underneath it
pkill eslint_d
rm .eslintcache
