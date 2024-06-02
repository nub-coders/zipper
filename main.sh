#!/bin/bash

source /home/u219967/venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
nohup python3 zipper.py &
