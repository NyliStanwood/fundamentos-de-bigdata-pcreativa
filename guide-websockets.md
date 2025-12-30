# WebSocket + Kafka Real-Time Flight Delay Prediction Architecture

## Overview

This guide documents the implementation of real-time flight delay predictions using WebSockets and Apache Kafka. The system enables clients to submit prediction requests and receive real-time results through bidirectional WebSocket communication.

## Architecture Components

### 1. **Kafka Message Queue**

- **Bootstrap Server**: `kafka:9092` (Docker internal network)
- **Topics**:
  - `flight-delay-ml-request`: Receives prediction requests from Flask
  - `flight-delay-ml-response`: Broadcasts prediction results to WebSocket clients

### 2. **Spark Streaming Pipeline** (MakePrediction.scala)

The Spark application performs the following tasks:

```
Input (Kafka) → JSON Parse → Feature Engineering → ML Model → Output
                                                        ↓
                                            ┌─────────┴─────────┐
                                            ↓                   ↓
                                        MongoDB           Kafka Output
                                    (Persistence)      (WebSocket Relay)
```

#### Input Processing

- Consumes from `flight-delay-ml-request` topic
- Parses JSON flight data with the following schema:
  - `Origin`, `Dest`, `Carrier`: Flight routing
  - `DepDelay`, `Distance`: Numerical features
  - `DayOfWeek`, `DayOfYear`, `DayOfMonth`: Temporal features
  - `FlightDate`, `Timestamp`: Date/time information
  - `UUID`: Unique request identifier (critical for matching)

#### Feature Engineering

1. String indexing for categorical columns: `Carrier`, `Origin`, `Dest`, `Route`
2. Vector assembly for numerical features: `DepDelay`, `Distance`, `DayOfMonth`, `DayOfWeek`, `DayOfYear`, indexed columns
3. Preprocessing with configured ML models

#### Model Inference

- Applies pre-trained Random Forest classifier from `/practica_creativa/models/`
- Outputs prediction classes:
  - `0`: Early (15+ minutes early)
  - `1`: Slightly Early (0-15 minutes early)
  - `2`: Slightly Late (0-30 minutes delay)
  - `3`: Very Late (30+ minutes late)

#### Dual Output Streams

1. **MongoDB**: Persists all predictions to `agile_data_science.flight_delay_ml_response` collection
2. **Kafka**: Broadcasts predictions as JSON to clients waiting on `flight-delay-ml-response`

### 3. **Flask WebSocket Server** (predict_flask.py)

#### Kafka Producer (Request Side)

- Sends prediction requests to `flight-delay-ml-request` topic
- Generates unique UUID for each request
- Preserves UUID through entire pipeline for request/response matching

```python
unique_id = str(uuid.uuid4())
prediction_features['UUID'] = unique_id
message_bytes = json.dumps(prediction_features).encode()
producer.send(PREDICTION_TOPIC, message_bytes)
response = {"status": "OK", "id": unique_id}
```

#### Kafka Consumer Thread (Response Side)

- Background thread consumes from `flight-delay-ml-response` topic
- Listens continuously for new predictions
- **Important Configuration**:
  - `auto_offset_reset='latest'`: Only reads messages arriving after startup
  - This means predictions must arrive after the server starts
  - For production, consider `'earliest'` with consumer group management

```python
def kafka_consumer_thread():
    consumer = KafkaConsumer(
        RESPONSE_PREDICTION_TOPIC,
        bootstrap_servers=['kafka:9092'],
        api_version=(0, 10),
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='latest',  # Only new messages
        enable_auto_commit=True
    )

    for message in consumer:
        prediction_result = message.value
        request_id = prediction_result.get('UUID')
        if request_id:
            socketio.emit('prediction_ready', prediction_result, room=request_id)
```

#### WebSocket Room System

- Uses `socket.io` room-based messaging
- Each unique request ID = one room
- When prediction arrives, it's emitted to the specific client room
- Prevents cross-contamination of results between concurrent requests

```python
@socketio.on('join')
def on_join(data):
    request_id = data.get('request_id')
    if request_id:
        join_room(request_id)
        emit('joined', {'room': request_id})
```

### 4. **Client-Side WebSocket (flight_delay_predict_websocket.js)**

#### Connection & Room Management

```javascript
const socket = io(); // Connect to server

socket.on("connect", function () {
  console.log("WebSocket connected");
});

$("#flight_delay_classification").submit(function (event) {
  event.preventDefault();

  // Submit form via POST
  $.post(url, $form.serialize(), function (data) {
    var response = JSON.parse(data);

    if (response.status === "OK") {
      // Join room for this specific request
      socket.emit("join", {
        request_id: response.id, // The UUID
      });

      console.log("Waiting for prediction with ID:", response.id);
    }
  });
});
```

#### Result Reception

```javascript
socket.on("prediction_ready", function (payload) {
  console.log("Prediction received:", payload);
  renderPage(payload); // Display result
});
```

## Data Flow Diagram

```
┌─────────────┐
│   Browser   │
│  (Client)   │
└──────┬──────┘
       │ (POST /classify_realtime)
       ↓
┌──────────────────────────────────┐
│   Flask WebSocket Server         │
│  - Creates UUID                  │
│  - Sends to Kafka Producer       │
│  - Returns {"id": UUID}          │
└──────────────────────────────────┘
       │
       │ (to flight-delay-ml-request)
       ↓
   ┌────────┐
   │ Kafka  │
   └────────┘
       │
       │ (from flight-delay-ml-request)
       ↓
┌──────────────────────────────────┐
│   Spark Streaming Pipeline       │
│  - Parse & Feature Engineer      │
│  - ML Model Inference            │
│  - Write to MongoDB              │
│  - Write to Kafka (response)     │
└──────────────────────────────────┘
       │
       │ (to flight-delay-ml-response)
       ↓
   ┌────────┐
   │ Kafka  │
   └────────┘
       │
       │ (from flight-delay-ml-response)
       ↓
┌──────────────────────────────────┐
│ Kafka Consumer Thread (Flask)    │
│  - Listen for UUID match         │
│  - Emit via WebSocket.io         │
└──────────────────────────────────┘
       │
       │ (socket.emit to room)
       ↓
┌─────────────┐
│   Browser   │
│  (Displays) │
└─────────────┘
```

## Key Implementation Details

### UUID Matching (Critical)

- **Flask generates UUID** when request is submitted
- **Spark preserves UUID** through entire pipeline
- **WebSocket room name** = UUID
- **Kafka message contains UUID** for identification
- This ensures clients only receive their own predictions

### Kafka Version Compatibility

The system requires **matching Kafka and Spark versions**:

```dockerfile
# Dockerfile.sparksubmit
--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3
```

- **Kafka Connector**: `3.5.3` (matches Spark version)
- **Previous Issue**: Using `3.1.2` caused `NoSuchMethodError: toAttributes()`
- **Root Cause**: Kafka write APIs changed between Spark 3.1 and 3.5

### Topic Initialization

Topics are auto-created on startup via `kafka-init` service:

```bash
/opt/kafka/bin/kafka-topics.sh --create \
  --bootstrap-server kafka:9092 \
  --replication-factor 1 \
  --partitions 1 \
  --topic flight-delay-ml-request \
  --if-not-exists

/opt/kafka/bin/kafka-topics.sh --create \
  --bootstrap-server kafka:9092 \
  --replication-factor 1 \
  --partitions 1 \
  --topic flight-delay-ml-response \
  --if-not-exists
```

## Dependencies Added

### Python Packages (resources/requirements.txt)

```
flask-socketio==5.6.0      # WebSocket support
python-socketio==5.16.0    # Socket.IO protocol
python-engineio==4.13.0    # Engine.IO transport
bidict==0.23.1             # Room/event mapping
eventlet==0.40.4           # Async I/O
greenlet==3.2.4            # Lightweight threading
simple-websocket==1.1.0    # WebSocket transport
wsproto==1.2.0             # WebSocket protocol
h11==0.16.0                # HTTP protocol
```

### JavaScript Libraries

```html
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
```

## File Changes Summary

### New Files

1. **`resources/web/static/flight_delay_predict_websocket.js`**: Client-side WebSocket logic
2. **`resources/check_kafka_topic.py`**: Utility to inspect Kafka messages

### Modified Files

1. **`Dockerfile.sparksubmit`**: Updated Kafka connector from 3.1.2 → 3.5.3
2. **`docker-compose.yml`**: Added `flight-delay-ml-response` topic creation
3. **`flight_prediction/src/main/scala/es/upm/dit/ging/predictor/MakePrediction.scala`**: Added Kafka producer + console logging
4. **`resources/web/predict_flask.py`**: Added Flask-SocketIO, Kafka consumer thread, WebSocket events
5. **`resources/requirements.txt`**: Added WebSocket dependencies
6. **`resources/web/templates/flight_delays_predict_kafka.html`**: Updated to use WebSocket instead of polling
7. **`resources/web/templates/all_airlines.html`**: Added link to WebSocket prediction page

## Running the System

### Start All Services

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Monitor Spark Pipeline

```bash
docker-compose logs -f sparksubmit
```

Look for:

```
>>> STARTING KAFKA WRITE STREAM...
✓✓✓ PREDICTIONS NOW POSTED TO KAFKA TOPIC 'flight-delay-ml-response' ✓✓✓
```

### Access Web Interface

1. Navigate to `http://127.0.0.1:5001/`
2. Click link to `/flights/delays/predict_kafka`
3. Fill in flight parameters:
   - Departure Delay: 5
   - Carrier: AA
   - Date: 2016-12-25
   - Origin: ATL
   - Destination: SFO
4. Click Submit
5. Result displays in real-time via WebSocket

### Debug Kafka Messages

```bash
# Check all messages in response topic
docker-compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic flight-delay-ml-response \
  --from-beginning
```

Or use the Python utility:

```bash
python resources/check_kafka_topic.py
```

## Troubleshooting

### Issue: "io is not defined" Error

**Solution**: Ensure Socket.IO script is loaded without integrity errors

```html
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
```

Remove any `integrity` or `crossorigin` attributes that don't match the CDN.

### Issue: Kafka Producer/Consumer Connection Failed

**Solution**:

- Inside containers: use `kafka:9092` (service name)
- From host machine: use `localhost:9092` (exposed port)

### Issue: UUID Mismatch - Predictions Not Received

**Solutions**:

1. Verify UUID is preserved through pipeline: `docker-compose logs sparksubmit | grep UUID`
2. Check Kafka message format: `docker-compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic flight-delay-ml-response --from-beginning`
3. Verify Spark is writing to Kafka (not just MongoDB)

### Issue: NoSuchMethodError in Kafka Writer

**Solution**: Ensure Kafka connector version matches Spark version in `Dockerfile.sparksubmit`

- Spark 3.5.3 requires `spark-sql-kafka-0-10_2.12:3.5.3`
- Using older versions (e.g., 3.1.2) causes compatibility errors

## Performance Considerations

### Latency

- Expected latency: 5-15 seconds (mostly Spark processing)
- Kafka messaging overhead: < 1 second
- WebSocket latency: negligible (< 100ms)

### Scalability

- Current setup: Single Kafka partition, single consumer
- For 1000+ concurrent users:
  - Increase Kafka partitions
  - Use consumer groups
  - Scale Flask instances with load balancer
  - Implement connection pooling for MongoDB

### Message Retention

- Kafka default: 7 days
- MongoDB: Indefinite (until manual cleanup)
- For memory-constrained environments, adjust Kafka retention:
  ```bash
  docker-compose exec kafka /opt/kafka/bin/kafka-configs.sh \
    --bootstrap-server localhost:9092 \
    --entity-type topics \
    --entity-name flight-delay-ml-response \
    --alter \
    --add-config retention.ms=86400000  # 24 hours
  ```

## Next Steps

### Production Hardening

1. Implement Kafka consumer groups for fault tolerance
2. Add error handling and retry logic in Spark
3. Implement request timeout (5 minute max wait)
4. Add logging and monitoring for all components
5. Implement authentication for Kafka/MongoDB
6. Use connection pooling for Kafka producers/consumers

### Feature Enhancements

1. Batch prediction requests (submit multiple flights at once)
2. Add historical prediction accuracy tracking
3. Implement model versioning
4. Add A/B testing infrastructure
5. Real-time model performance monitoring

### Monitoring & Logging

1. Add Prometheus metrics export from Spark
2. Set up ELK stack (Elasticsearch, Logstash, Kibana)
3. Monitor Kafka lag per consumer group
4. Track Flask-SocketIO connection metrics
5. Alert on pipeline failures

## References

- [Socket.IO Documentation](https://socket.io/docs/)
- [Kafka Streaming with Spark](https://spark.apache.org/docs/3.5.3/structured-streaming-kafka-integration.html)
- [Flask-SocketIO](https://flask-socketio.readthedocs.io/)
- [Kafka Docker Image](https://hub.docker.com/r/apache/kafka)
