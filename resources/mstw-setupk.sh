#!/usr/bin/env bash
cd /home/ibdn/Downloads/kafka_2.12-3.9.0
rm -rf /tmp/kafka-logs /tmp/kraft-combined-logs
KAFKA_CLUSTER_ID="$(bin/kafka-storage.sh random-uuid)"
bin/kafka-storage.sh format -t $KAFKA_CLUSTER_ID -c config/kraft/server.properties
bin/kafka-server-start.sh config/kraft/server.properties


