#!/bin/bash

python3 -m pip install --upgrade pip
python3 -m pip install --upgrade build
python -m build
python3 -m pip install --upgrade twine
python3 -m twine upload dist/*
