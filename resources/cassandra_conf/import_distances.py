import argparse
import json
import os
import sys
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import origin/dest distances JSONL into Cassandra")
    parser.add_argument(
        "--file",
        default="/data/origin_dest_distances.jsonl",
        help="Path to origin_dest_distances JSONL file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not os.path.exists(args.file):
        print(f"File not found: {args.file}")
        sys.exit(1)

    host = os.getenv("CASSANDRA_HOST", "cassandra")
    port = int(os.getenv("CASSANDRA_PORT", "9042"))
    user = os.getenv("CASSANDRA_USER", "cassandra")
    password = os.getenv("CASSANDRA_PASSWORD", "cassandra")

    auth = PlainTextAuthProvider(username=user, password=password)
    cluster = Cluster([host], port=port, auth_provider=auth)
    session = cluster.connect("agile_data_science")

    insert_stmt = session.prepare(
        """
        INSERT INTO origin_dest_distances (origin, dest, distance)
        VALUES (?, ?, ?)
        """
    )

    count = 0
    with open(args.file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            origin = data.get("origin") or data.get("Origin") or ""
            dest = data.get("dest") or data.get("Dest") or ""
            distance_val = data.get("distance")
            if distance_val is None:
                distance_val = data.get("Distance", 0)
            session.execute(
                insert_stmt,
                (
                    origin,
                    dest,
                    float(distance_val),
                ),
            )
            count += 1
            if count % 1000 == 0:
                print(f"Imported {count} records...")

    print(f"Import complete. Total records: {count}")
    cluster.shutdown()


if __name__ == "__main__":
    main()