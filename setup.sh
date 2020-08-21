#!/bin/sh
sh pm makemigrations codex_api
sh pm migrate
./superuser.sh
