#!/bin/bash

pip install --upgrade pip
pip install -r requirements.txt
nohup python3 zipper.py &
