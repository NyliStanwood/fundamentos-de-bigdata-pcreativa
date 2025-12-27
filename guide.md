# Flight Delay Prediction System - System Guide

## Overview

- **Purpose**: This repository implements a small end-to-end predictive system for flight delays used in a practical/laboratory setting. It demonstrates both batch training with PySpark and Spark MLlib and a realtime prediction pipeline using Kafka, Spark Streaming, and a Flask web front end.
- **Audience**: Master degree students who need a concise but technically accurate view of the system components, their responsibilities, and how to run and extend the lab.

## Architecture

- **Front-end**: A Flask web application (`resources/web/predict_flask.py`) that accepts prediction requests from users and either serves batch/regression endpoints or emits Kafka messages for realtime classification requests.
- **Realtime pipeline**: Web app → Kafka topic `flight-delay-ml-request` → Spark Streaming job consumes requests, uses the saved model, writes results to MongoDB → web client polls MongoDB for results.
- **Batch pipeline**: Historical data under `data/` → `resources/train_spark_mllib_model.py` performs feature extraction, training, and saves models to `models/` → `resources/make_predictions.py` can run batch predictions over daily input files and write outputs under `data/prediction_results_daily.json/`.
- **Orchestration**: Optional Apache Airflow DAG defined in `resources/airflow/setup.py` (used to schedule or trigger training tasks).

## Key Components (files & folders)

- **`data/`**: Raw and processed data used for training and prediction tasks.
- **`resources/train_spark_mllib_model.py`**: Script that builds feature pipelines, trains a RandomForest classifier with Spark MLlib, and writes model artifacts to `models/`.
- **`resources/make_predictions.py`**: Spark job that loads the saved models and produces batch prediction outputs (JSON) partitioned by date.
- **`resources/web/predict_flask.py`**: Flask app that provides user pages, APIs, and the logic to publish realtime prediction requests to Kafka and to read results from MongoDB.
- **`resources/airflow/setup.py`**: Airflow DAG definition for model training. See the `Airflow DAG Behavior` section below for specifics.
- **`resources/import_distances.sh`** and **`resources/download_data.sh`**: helper scripts to import required geographic/distance data and to fetch sample datasets.
- **`resources/*` static & templates**: front-end assets and Jinja templates under `resources/web/static/` and `resources/web/templates/`.

## Data Flow & Workflows (high level)

### Training (batch)
- **Input**: historical flight features in `data/simple_flight_delay_features.jsonl.bz2` (or other files under `data/`).
- **Work**: `resources/train_spark_mllib_model.py` builds indexers, vector assembler and trains a RandomForest classifier. Models and helper artifacts (bucketizer, indexer models, vector assembler) are saved under `models/`.
- **Output**: trained model at e.g. `models/spark_random_forest_classifier.flight_delays.5.0.bin`.

### Batch prediction
- **Trigger**: run `resources/make_predictions.py` for a given date.
- **Work**: loads models, transforms daily request JSONs from `data/prediction_tasks_daily.json/<date>` and writes results to `data/prediction_results_daily.json/<date>`.

### Realtime prediction
- User posts a prediction request (via the web UI) to `predict_flask.py`.
- The Flask app publishes a message to Kafka (`flight-delay-ml-request`).
- A Spark Streaming consumer (not included as a single file here but described in the README/book) consumes requests, uses the saved model to classify, and inserts results into MongoDB.
- The client polls the server (via a response endpoint) and displays the result once present in MongoDB.

## Airflow DAG Behavior (practical points)

- **DAG id**: `agile_data_science_batch_prediction_model_training` (defined in `resources/airflow/setup.py`).
- **Schedule**: `schedule_interval=None` — the DAG is not scheduled automatically. It is designed to be triggered manually or externally unless you change `schedule_interval` to something like `'@daily'` or a cron expression.
- **Start date**: configured with `start_date = iso8601.parse_date("2016-12-01")`, but with `schedule_interval=None` this does not create periodic runs.
- **Retries / failure handling**:
  - `default_args` sets `'retries': 3` and `'retry_delay': timedelta(minutes=5)`. That means Airflow will attempt a failing task up to 3 retry attempts (waiting 5 minutes between attempts). If the task still fails after retries, the task state becomes `failed` and downstream tasks will not run (unless you change trigger rules).
  - `depends_on_past` is `False`, so runs do not require the previous run to have succeeded.
  - There are no `email_on_failure`, `on_failure_callback` or similar notification callbacks configured in the DAG's `default_args` — add them if you want alerts on failure.
  - The `train_classifier_model_operator` is a `BashOperator` invoking `spark-submit`; if the Spark job exits with a non-zero code, the BashOperator will fail and follow the retry logic above.

## How to run locally (quick commands)

### Create Python venv and install deps
```powershell
python -m venv env
env\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Download example data (from README)
```powershell
resources\download_data.sh
```

### Import distances into MongoDB
```powershell
resources\import_distances.sh
```

### Train model (PySpark)
```powershell
python resources\train_spark_mllib_model.py .
```

### Run batch predictions for a date
```powershell
python resources\make_predictions.py 2016-12-01 .
```

### Start the Flask web app
```powershell
setx PROJECT_HOME "C:\path\to\practica_creativa"
cd resources\web
python predict_flask.py
```

## Operational notes & common pitfalls

- **Spark environment**: The scripts rely on having `spark-submit`/Spark available and on matching versions for connectors. The README highlights recommended versions (Spark 3.5.3, Scala 2.12, Mongo connector and Kafka packages).
- **MongoDB**: The web UI and prediction pipeline read/write to MongoDB. Make sure MongoDB is running and reachable on default ports or adjust connection settings.
- **Kafka**: For realtime prediction you must start Kafka and create the topic `flight-delay-ml-request` before using the realtime path.
- **Model artifacts path**: Both training and prediction scripts rely on a `PROJECT_HOME` or explicit base path; ensure `PROJECT_HOME` is set or pass `.`/the base path argument when invoking the scripts.

## Where to look next (for extension or study)

- **Spark Streaming consumer**: study the streaming pieces in the book/chapter code that subscribe to Kafka and call into the same model artifacts used by batch code — this demonstrates code reuse between batch and realtime.
- **Airflow**: if you want scheduled training, change `schedule_interval` in `resources/airflow/setup.py` and optionally add `email_on_failure` or `on_failure_callback` to `default_args`.
- **Metrics & monitoring**: add `on_failure_callback` or alerting integrations (Slack/email) to Airflow tasks, and add logging/metrics to Spark jobs for operational visibility.

## Technology Stack Overview

This section describes each major technology used in the system, the specific components/tools involved, and their purposes.

### 1. Apache Spark & PySpark

**What**: Distributed data processing and machine learning framework.

**Components used**:
- **PySpark SQL**: Used in both `train_spark_mllib_model.py` and `make_predictions.py` to load JSON data, build DataFrames, apply transformations (feature engineering), and write results.
- **Spark MLlib**: Machine learning library used for feature engineering (`StringIndexer`, `VectorAssembler`, `Bucketizer`) and classification (`RandomForestClassifier`).
- **Spark Streaming**: (Described in book/external code) Consumes Kafka messages in real-time and applies the same model artifacts used in batch for online predictions.
- **spark-submit**: Command-line tool used to launch Spark jobs (via Airflow's `BashOperator`).

**Purpose**: Enable large-scale distributed training and batch/realtime prediction over flight delay data.

### 2. Apache Kafka

**What**: Event streaming/message queue platform.

**Components used**:
- **Kafka Topic** (`flight-delay-ml-request`): Created during setup; used to decouple the Flask web app (producer) from the Spark Streaming consumer.
- **Kafka Producer** (in Flask app): Publishes prediction requests as JSON messages.
- **Kafka Consumer** (in Spark Streaming): Subscribes to prediction requests and processes them in micro-batches.

**Purpose**: Enable asynchronous, decoupled communication between the web front-end and the realtime prediction engine.

### 3. Spark Streaming

**What**: Micro-batch streaming extension of Spark.

**Components used**:
- **Streaming DataFrame/RDD API**: Applies the same ML transformations and model inference as batch.
- **Kafka integration**: Natively consumes from Kafka topics.
- **MongoDB write adapter**: Outputs prediction results to MongoDB for client retrieval.

**Purpose**: Process streaming prediction requests in near-real-time with the same code/models used in batch, demonstrating unified batch/streaming ML.

### 4. MongoDB

**What**: Document-oriented NoSQL database.

**Components used**:
- **Collections**: 
  - `flight_delay_ml_response`: Stores prediction results (used by Spark Streaming to write results and by Flask client to poll for answers).
  - `on_time_performance`, `flights_by_month`, `airlines`, `airplanes_per_carrier`: Historical and lookup data.
  - Other aggregated collections for reporting/UI.
- **Indexing**: Created via `resources/import_distances.sh` for fast geographic distance lookups.

**Purpose**: Centralized, flexible document store for both operational data (prediction results) and reference/analytics data.

### 5. Flask

**What**: Python web framework for building HTTP APIs and serving web pages.

**Components used**:
- **Routes**: Define endpoints like `/flights/delays/predict_kafka`, `/flights/search`, `/airline/<code>`, etc.
- **Template rendering**: Jinja2 templates in `resources/web/templates/` render HTML pages with data from MongoDB.
- **JSON APIs**: Endpoints that emit JSON (e.g., `/flights/delays/predict/classify_realtime/response/`) for client polling.
- **Form handling**: POST endpoints like `/flights/delays/predict/classify` accept user input and orchestrate prediction requests.
- **Kafka producer integration**: Publishes prediction requests to Kafka.
- **MongoDB client**: Queries for flight data, distance data, and reads back prediction results.

**Purpose**: Serve the user-facing web application, handle form submissions, and bridge the web UI to the prediction pipeline.

### 6. Elasticsearch (optional, for search)

**What**: Full-text search and analytics engine.

**Components used**:
- **Index**: Stores aircraft and flight records for faceted search.
- **Search API**: Used in `/airplanes` and `/flights/search` endpoints for flexible, fast queries over large datasets.

**Purpose**: Provide efficient full-text and faceted search over historical flights and aircraft data.

### 7. Apache Airflow

**What**: Workflow orchestration and scheduling platform.

**Components used**:
- **DAG** (Directed Acyclic Graph): `agile_data_science_batch_prediction_model_training` defined in `resources/airflow/setup.py`.
- **BashOperator**: Wraps `spark-submit` commands to run training and prediction jobs.
- **Task dependencies**: Currently set to `None`; can be chained to enforce sequential execution.
- **Scheduling**: `schedule_interval=None` by default (manual trigger); change to `'@daily'` or cron for periodic runs.
- **Retry logic**: Built-in retry mechanism (3 retries, 5-minute delay) for fault tolerance.
- **Web UI**: Monitor DAG runs, task logs, and trigger runs manually via http://localhost:8080.

**Purpose**: Schedule and orchestrate periodic model training, provide visibility into job execution, and enable fault recovery.

### 8. Python (core language)

**What**: Programming language for scripting and glue logic.

**Key libraries**:
- **pyspark**: PySpark SQL and MLlib APIs.
- **findspark**: Locates and initializes Spark in a Python environment.
- **pymongo**: Python driver for MongoDB reads/writes.
- **kafka-python**: Python Kafka producer/consumer for messaging.
- **flask**: Web framework.
- **joblib**: Model persistence (used in the README for sklearn models).
- **iso8601**: Date/time parsing for flight prediction dates.
- **pyelasticsearch**: Python client for Elasticsearch (optional).

**Purpose**: Glue all components together; implement business logic for feature engineering, model training/inference, and web orchestration.

### 9. Scala & SBT (for Spark MLlib production code)

**What**: Scala is the native JVM language for Spark; SBT is its build tool.

**Components used** (briefly mentioned in README):
- **`flight_prediction/` folder**: Contains Scala code (`src/main/scala/es/upm/`) for Spark jobs.
- **`build.sbt`**: Defines dependencies (MongoDB Spark connector, Kafka packages, etc.).
- **Compilation**: `sbt` compiles Scala to JAR files, which are then run via `spark-submit`.

**Purpose**: Write production Spark MLlib jobs; compile and package them for distributed execution.

### 10. Shell Scripting (Bash)

**What**: Unix shell for system automation.

**Components used**:
- **`resources/download_data.sh`**: Fetches sample flight delay datasets.
- **`resources/import_distances.sh`**: Imports geographic distance reference data into MongoDB.

**Purpose**: Simplify environment setup and data initialization for students.

### 11. HTML/CSS/JavaScript (Front-end)

**What**: Client-side web technologies.

**Components used**:
- **Templates**: Jinja2 templates in `resources/web/templates/` (e.g., `flight_delays_predict_kafka.html`, `flight.html`).
- **Static assets**: CSS, JavaScript libraries (`d3.v3.min.js`, `nv.d3.min.js`, `bootstrap.min.css`, etc.) in `resources/web/static/`.
- **JavaScript**: Custom scripts (`app.js`, `flight_delay_predict_polling.js`) for polling results and visualizing data.

**Purpose**: Render interactive web pages and visualizations; implement client-side polling for asynchronous prediction results.

### 12. Docker (optional)

**What**: Containerization platform.

**Components used** (mentioned in README):
- **MongoDB container**: `docker run --name mongo ... mongo:7.0.17` for easy MongoDB setup.
- **Alternative to local installation**: Provides isolated, reproducible environments.

**Purpose**: Simplify infrastructure setup without system-level package management.

## Summary of Data & Control Flow by Technology

| Stage | Technology | Purpose |
|-------|------------|---------|
| **Data ingestion** | Bash scripts, Python | Download and import flight delay data and distance references. |
| **Feature engineering** | PySpark SQL, Spark MLlib | Transform raw JSON into feature vectors suitable for ML. |
| **Model training** | Spark MLlib (RandomForest) | Train classifier on historical data; save artifacts (models, indexers, etc.). |
| **Batch prediction** | PySpark, Spark MLlib | Load saved models and score daily prediction requests. |
| **Realtime message queue** | Kafka | Decouple web requests from prediction engine. |
| **Realtime processing** | Spark Streaming, Kafka | Consume requests, apply model, write results. |
| **Result storage** | MongoDB | Persist predictions and historical/lookup data. |
| **Web front-end** | Flask, HTML/CSS/JS | Serve UI, accept user input, publish to Kafka, poll for results. |
| **Orchestration & scheduling** | Airflow | Schedule training jobs, provide visibility, enable retries. |
| **Search/analytics** | Elasticsearch | Optional fast indexing and full-text search over flights/aircraft. |



