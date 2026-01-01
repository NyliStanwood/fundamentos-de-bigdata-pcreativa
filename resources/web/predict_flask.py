import sys, os, re
from flask import Flask, render_template, request
from cassandra.cluster import Cluster  # Cassandra driver
from bson import json_util

# Configuration details
import config

# Helpers for search and prediction APIs
import predict_utils

# Set up Flask, Mongo and Elasticsearch
app = Flask(__name__)

# Initialize SocketIO
from flask_socketio import SocketIO, emit, join_room
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

from cassandra.auth import PlainTextAuthProvider
# --- Cassandra connection setup (replaces MongoDB) ---
auth_provider = PlainTextAuthProvider(username='root', password='example')
cluster = Cluster(['cassandra'], auth_provider=auth_provider)
session = cluster.connect('agile_data_science')
# --- End Cassandra connection setup ---

import json

# Date/time stuff
import iso8601
import datetime

# Setup Kafka
from kafka import KafkaProducer, KafkaConsumer
producer = KafkaProducer(bootstrap_servers=['kafka:9092'],api_version=(0,10))
PREDICTION_TOPIC = 'flight-delay-ml-request'
RESPONSE_PREDICTION_TOPIC = 'flight-delay-ml-response'

import uuid
import threading

# Kafka consumer background thread
# it joins a WebSocket room named after its unique UUID. 
# Later, when the Kafka consumer thread receives a prediction result with that UUID, 
# it emits the "prediction_ready" event specifically to the room with that UUID. 
# Only the client that joined that room receives the event, 
# ensuring the correct client gets its prediction result.
def kafka_consumer_thread():
    """Background thread that consumes from Kafka response topic and emits to WebSocket clients"""
    consumer = KafkaConsumer(
        RESPONSE_PREDICTION_TOPIC,
        bootstrap_servers=['kafka:9092'],
        api_version=(0, 10),
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='latest',
        enable_auto_commit=True
    )
    
    print(f"Kafka consumer thread started, listening to {RESPONSE_PREDICTION_TOPIC}")
    
    for message in consumer:
        try:
            prediction_result = message.value
            request_id = prediction_result.get('UUID')
            
            if request_id:
                print(f"Received prediction for UUID: {request_id}")
                # Emit to the specific room (client waiting for this UUID)
                # THIS IS THE IMPORTANT HOOK !!!!
                # this will trigger the "prediction_ready" event to do a RENDER on the client side
                socketio.emit('prediction_ready', prediction_result, room=request_id)
        
        except Exception as e:
            print(f"Error processing Kafka message: {e}")

# Start the Kafka consumer in a background thread
consumer_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
consumer_thread.start()

# WebSocket event handlers
@socketio.on('join')
def on_join(data):
    """Handle client joining a room based on their request_id"""
    request_id = data.get('request_id')
    if request_id:
        join_room(request_id)
        print(f"Client joined room: {request_id}")
        emit('joined', {'room': request_id})


# Controller: Fetch an airplane entity page
@app.route("/")
@app.route("/airlines")

# Make our API a post, so a search engine wouldn't hit it. 
# only accepts HTTP POST requests, 
# which helps prevent accidental triggering by web crawlers or search engines.
@app.route("/flights/delays/predict/classify_realtime", methods=['POST'])
def classify_flight_delays_realtime():
  """POST API for classifying flight delays"""
  
  # Define the form fields to process, along with their expected types
  # this helps in converting the form inputs to the correct types
  api_field_type_map = \
    {
      "DepDelay": float,
      "Carrier": str,
      "FlightDate": str,
      "Dest": str,
      "FlightNum": str,
      "Origin": str
    }

  # Fetch the values for each field from the form object
  api_form_values = {}
  # Iterate over each field and get its value and convert to the correct type from the form
  for api_field_name, api_field_type in api_field_type_map.items():
    api_form_values[api_field_name] = request.form.get(api_field_name, type=api_field_type)
  
  # Set the direct values, which excludes Date
  prediction_features = {} # Dictionary to hold features for prediction

  # Copy over direct values from form sent by user
  for key, value in api_form_values.items():
    prediction_features[key] = value
  
  # Set the "derived features", derived from other inputs and lookups
  
  # Get the Distance between Origin and Dest from Cassandra
  print("getting distance from cassandra...")
  prediction_features['Distance'] = predict_utils.get_flight_distance(
    session, api_form_values['Origin'], 
    api_form_values['Dest']
  )
  print(f"Derived Distance: {prediction_features['Distance']} for {api_form_values['Origin']} to {api_form_values['Dest']}")
  
  # Turn the date into DayOfYear, DayOfMonth, DayOfWeek, based on the FlightDate
  date_features_dict = predict_utils.get_regression_date_args(
    api_form_values['FlightDate']
  )

  # Add the derived date features to the prediction features
  for api_field_name, api_field_value in date_features_dict.items():
    prediction_features[api_field_name] = api_field_value
  
  # Add a timestamp
  prediction_features['Timestamp'] = predict_utils.get_current_timestamp()
  
  # Create a unique ID for this message
  unique_id = str(uuid.uuid4())
  prediction_features['UUID'] = unique_id
  
  # Send the message to Kafka for processing
  # Serialize the features to JSON and send to Kafka
  message_bytes = json.dumps(prediction_features).encode() # Convert to bytes

  # Send to Kafka topic
  producer.send(PREDICTION_TOPIC, message_bytes)

  response = {"status": "OK", "id": unique_id} # Return the unique ID to the client for polling

  return json_util.dumps(response)



@app.route("/flights/delays/predict_kafka")
def flight_delays_page_kafka():
  """Serves flight delay prediction page with polling form"""
  
  form_config = [
    {'field': 'DepDelay', 'label': 'Departure Delay', 'value': 5},
    {'field': 'Carrier', 'value': 'AA'},
    {'field': 'FlightDate', 'label': 'Date', 'value': '2016-12-25'},
    {'field': 'Origin', 'value': 'ATL'},
    {'field': 'Dest', 'label': 'Destination', 'value': 'SFO'}
  ]
  
  return render_template('flight_delays_predict_kafka.html', form_config=form_config)

## It executes a CQL query to select all columns from the flight_delay_ml_response table 
# where the UUID matches the provided unique_id. 
# If a matching row is found, it converts the result to a dictionary and 
# returns it with status "OK"; otherwise, it returns status "WAIT"
@app.route("/flights/delays/predict/classify_realtime/response/<unique_id>")
def classify_flight_delays_realtime_response(unique_id):
  """
  Serves predictions to polling requestors
  Updated: Now queries Cassandra instead of MongoDB
  """
  # parametrized query, will insert unique_id safely
  query = "SELECT * FROM flight_delay_ml_response WHERE UUID=%s LIMIT 1"
  row = session.execute(query, (unique_id,)).one()
  response = {"status": "WAIT", "id": unique_id}
  if row:
    # Convert row to dict for JSON serialization
    response["status"] = "OK"
    response["prediction"] = dict(row._asdict())
  return json_util.dumps(response)

def shutdown_server():
  func = request.environ.get('werkzeug.server.shutdown')
  if func is None:
    raise RuntimeError('Not running with the Werkzeug Server')
  func()

@app.route('/shutdown')
def shutdown():
  shutdown_server()
  return 'Server shutting down...'

if __name__ == "__main__":
    socketio.run(
    app,
    debug=True,
    host='0.0.0.0',
    port='5001',
    allow_unsafe_werkzeug=True
  )
