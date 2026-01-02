#!/bin/bash

# Cassandra initialization script with user/password setup

set -e

echo "Starting Cassandra with custom initialization..."

# Start Cassandra in the background using the official entrypoint path
/usr/local/bin/docker-entrypoint.sh cassandra -f &
CASSANDRA_PID=$!

echo "Waiting for Cassandra to be ready..."
# Wait for Cassandra to be ready (check port 9042)
HOST="${CASSANDRA_HOST:-cassandra}"
for i in {1..60}; do
    if nc -z "$HOST" 9042 2>/dev/null; then
        echo "Cassandra is ready!"
        break
    fi
    echo "Waiting... ($i/60)"
    sleep 2
done
# Give Cassandra a bit more time to fully initialize CQL service
sleep 15

# Verify CQL is actually ready by testing a connection
echo "Verifying CQL service is ready..."
PASSWORD="cassandra"
for i in {1..60}; do
    if cqlsh "$HOST" -u cassandra -p "$PASSWORD" -e "describe cluster" >/dev/null 2>&1; then
        echo "CQL service is ready!"
        READY=1
        break
    fi
    echo "Waiting for CQL... ($i/60)"
    sleep 2
done

# Create admin user with password
echo "Setting up authentication..."
# Ensure password stays 'cassandra'
ADMIN_PASS="cassandra"
cqlsh "$HOST" -u cassandra -p "$ADMIN_PASS" -e "ALTER USER cassandra WITH PASSWORD '$ADMIN_PASS';" || true

# Create application user
echo "Creating application user..."
cqlsh "$HOST" -u cassandra -p "$ADMIN_PASS" -e "CREATE USER IF NOT EXISTS root WITH PASSWORD 'example' SUPERUSER;" || true

# Initialize schema
echo "Initializing database schema..."

KEYSPACE="agile_data_science"
SCHEMA1="/resources/cassandra_conf/table_origin_dest_distances.cql"
SCHEMA2="/resources/cassandra_conf/table_flight_delay_ml_response.cql"

cqlsh "$HOST" -u cassandra -p "$ADMIN_PASS" -e "CREATE KEYSPACE IF NOT EXISTS $KEYSPACE WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};"

if [ -f "$SCHEMA1" ]; then
    cqlsh "$HOST" -k "$KEYSPACE" -u cassandra -p "$ADMIN_PASS" -f "$SCHEMA1"
    echo "Schema table_origin_dest_distances initialized successfully!"
else
    echo "Warning: Schema file not found at $SCHEMA1"
fi

if [ -f "$SCHEMA2" ]; then
    cqlsh "$HOST" -k "$KEYSPACE" -u cassandra -p "$ADMIN_PASS" -f "$SCHEMA2"
    echo "Schema table_flight_delay_ml_response initialized successfully!"
else
    echo "Warning: Schema file not found at $SCHEMA2"
fi

echo "Running data download and import scripts..."

# Download data files
/resources/download_data.sh

# # Install Python cassandra-driver if needed
# pip3 install cassandra-driver

# Import origin_dest_distances JSONL data into Cassandra
echo "Importing origin_dest_distances data..."
DATA_FILE=/data/origin_dest_distances.jsonl
if [ -f "$DATA_FILE" ]; then
    python3 /resources/cassandra_conf/import_distances.py --file "$DATA_FILE"
else
    echo "Warning: origin_dest_distances.jsonl not found at $DATA_FILE"
fi

echo "Cassandra initialization complete!"

# Keep Cassandra running in foreground
wait $CASSANDRA_PID
