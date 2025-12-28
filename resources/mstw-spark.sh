#!/usr/bin/env bash
cd /home/ibdn/practica_creativa/flight_prediction
spark-submit \
  --class es.upm.dit.ging.predictor.MakePrediction \
  --master local[*] \
  --packages org.mongodb.spark:mongo-spark-connector_2.12:10.4.1,org.apache.spark:spark-sql-kafka-0-10_2.12:3.1.2 \
  target/scala-2.12/flight_prediction_2.12-0.1.jar


