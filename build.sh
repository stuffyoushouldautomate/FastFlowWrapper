#!/bin/bash

# Install build dependencies
apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    gcc \
    g++

# Upgrade pip
python -m pip install --upgrade pip

# Install wheel first
pip install wheel

# Install requirements
pip install -r requirements.txt 