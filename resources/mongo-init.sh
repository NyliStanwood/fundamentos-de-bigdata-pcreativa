#!/bin/bash
set -e

# This script runs automatically during MongoDB initialization
# by the docker-entrypoint.sh when the database is first created

echo "Waiting for MongoDB to be fully ready..."
sleep 10

echo "Running data download and import scripts..."

# Download data files
/resources/download_data.sh

# Import distances to MongoDB
/resources/import_distances.sh

echo "MongoDB initialization complete!"
