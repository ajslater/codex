#!/bin/sh
sh pm makemigrations
sh pm migrate
./superuser.sh
