#!/bin/bash

CD=$(pwd)

echo "starting"

cd /home/alfu64/Development/track-applications

source .venv/bin/activate

while true; do

echo "working"

python application-tracking.service.py

sleep 20

done