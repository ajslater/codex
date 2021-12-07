#!/bin/sh
docker compose up --exit-code-from "$1" "$1"
