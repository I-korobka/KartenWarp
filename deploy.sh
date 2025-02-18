#!/bin/bash
# deploy.sh - Run integration tests and build the package
set -e

echo "Running integration tests..."
python -m unittest discover -s tests

echo "Building package..."
python setup.py sdist bdist_wheel

echo "Deployment package built successfully."
