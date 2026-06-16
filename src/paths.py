#!/usr/bin/env python3
"""
Repo-relative path configuration. Replaces the old hardcoded container paths
(/mnt/user-data/outputs, /home/claude/...) so every script runs anywhere:
the fresh local clone, a student's machine, or CI. Override any path via the
matching environment variable.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR   = os.environ.get("H2_DATA_DIR",  os.path.join(ROOT, "data"))
MODELS_DIR = os.environ.get("H2_MODEL_DIR", os.path.join(ROOT, "models"))
RAW_DIR    = os.environ.get("H2_RAW_DIR",   os.path.join(DATA_DIR, "raw"))

for _d in (DATA_DIR, MODELS_DIR, RAW_DIR):
    os.makedirs(_d, exist_ok=True)
