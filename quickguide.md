**Overview**

- **Purpose**: This repository implements a small end-to-end predictive system for flight delays used in a practical/laboratory setting. It demonstrates both batch training with PySpark and Spark MLlib and a realtime prediction pipeline using Kafka, Spark Streaming, and a Flask web front end.
- **Audience**: Master degree students who need a concise but technically accurate view of the system components, their responsibilities, and how to run and extend the lab.

**Architecture**

- **Front-end**: A Flask web application (`resources/web/predict_flask.py`) that accepts prediction requests from users and either serves batch/regression endpoints or emits Kafka messages for realtime classification requests.
- **Realtime pipeline**: Web app -> Kafka topic `flight-delay-ml-request` -> Spark Streaming job consumes requests, uses the saved model, writes results to MongoDB -> web client polls MongoDB for results.
- **Batch pipeline**: Historical data under `data/` -> `resources/train_spark_mllib_model.py` performs feature extraction, training, and saves models to `models/` -> `resources/make_predictions.py` can run batch predictions over daily input files and write outputs under `data/prediction_results_daily.json/`.
- **Orchestration**: Optional Apache Airflow DAG defined in `resources/airflow/setup.py` (used to schedule or trigger training tasks).

**Key Components (files & folders)**

- **`data/`**: Raw and processed data used for training and prediction tasks.
- **`resources/train_spark_mllib_model.py`**: Script that builds feature pipelines, trains a RandomForest classifier with Spark MLlib, and writes model artifacts to `models/`.
- **`resources/make_predictions.py`**: Spark job that loads the saved models and produces batch prediction outputs (JSON) partitioned by date.
- **`resources/web/predict_flask.py`**: Flask app that provides user pages, APIs, and the logic to publish realtime prediction requests to Kafka and to read results from MongoDB.
- **`resources/airflow/setup.py`**: Airflow DAG definition for model training. See the `Airflow DAG Behavior` section below for specifics.
- **`resources/import_distances.sh`** and `resources/download_data.sh`: helper scripts to import required geographic/distance data and to fetch sample datasets.
- **`resources/*` static & templates**: front-end assets and Jinja templates under `resources/web/static/` and `resources/web/templates/`.

**Data Flow & Workflows (high level)**

- **Training (batch)**:
	- Input: historical flight features in `data/simple_flight_delay_features.jsonl.bz2` (or other files under `data/`).
	- Work: `resources/train_spark_mllib_model.py` builds indexers, vector assembler and trains a RandomForest classifier. Models and helper artifacts (bucketizer, indexer models, vector assembler) are saved under `models/`.
	- Output: trained model at e.g. `models/spark_random_forest_classifier.flight_delays.5.0.bin`.

- **Batch prediction**:
	- Trigger: run `resources/make_predictions.py` for a given date.
	- Work: loads models, transforms daily request JSONs from `data/prediction_tasks_daily.json/<date>` and writes results to `data/prediction_results_daily.json/<date>`.

- **Realtime prediction**:
	- User posts a prediction request (via the web UI) to `predict_flask.py`.
	- The Flask app publishes a message to Kafka (`flight-delay-ml-request`).
	- A Spark Streaming consumer (not included as a single file here but described in the README/book) consumes requests, uses the saved model to classify, and inserts results into MongoDB.
	- The client polls the server (via a response endpoint) and displays the result once present in MongoDB.

**Airflow DAG Behavior (practical points)**

- **DAG id**: `agile_data_science_batch_prediction_model_training` (defined in `resources/airflow/setup.py`).
- **Schedule**: `schedule_interval=None` — the DAG is not scheduled automatically. It is designed to be triggered manually or externally unless you change `schedule_interval` to something like `'@daily'` or a cron expression.
- **Start date**: configured with `start_date = iso8601.parse_date("2016-12-01")`, but with `schedule_interval=None` this does not create periodic runs.
- **Retries / failure handling**:
	- `default_args` sets `'retries': 3` and `'retry_delay': timedelta(minutes=5)`. That means Airflow will attempt a failing task up to 3 retry attempts (waiting 5 minutes between attempts). If the task still fails after retries, the task state becomes `failed` and downstream tasks will not run (unless you change trigger rules).
	- `depends_on_past` is `False`, so runs do not require the previous run to have succeeded.
	- There are no `email_on_failure`, `on_failure_callback` or similar notification callbacks configured in the DAG's `default_args` — add them if you want alerts on failure.
	- The `train_classifier_model_operator` is a `BashOperator` invoking `spark-submit`; if the Spark job exits with a non-zero code, the BashOperator will fail and follow the retry logic above.

**How to run locally (quick commands)**

- **Create Python venv and install deps**:
```powershell
python -m venv env
env\Scripts\Activate.ps1
pip install -r requirements.txt
```

- **Download example data (from README)**:
```powershell
resources\download_data.sh
```

- **Import distances into MongoDB**:
```powershell
resources\import_distances.sh
```

- **Train model (PySpark)**:
```powershell
python resources\train_spark_mllib_model.py .
```

- **Run batch predictions for a date**:
```powershell
python resources\make_predictions.py 2016-12-01 .
```

- **Start the Flask web app**:
```powershell
setx PROJECT_HOME "C:\\path\\to\\practica_creativa"
cd resources\web
python predict_flask.py
```

**Operational notes & common pitfalls**

- **Spark environment**: The scripts rely on having `spark-submit`/Spark available and on matching versions for connectors. The README highlights recommended versions (Spark 3.5.3, Scala 2.12, Mongo connector and Kafka packages).
- **MongoDB**: The web UI and prediction pipeline read/write to MongoDB. Make sure MongoDB is running and reachable on default ports or adjust connection settings.
- **Kafka**: For realtime prediction you must start Kafka and create the topic `flight-delay-ml-request` before using the realtime path.
- **Model artifacts path**: Both training and prediction scripts rely on a `PROJECT_HOME` or explicit base path; ensure `PROJECT_HOME` is set or pass `.`/the base path argument when invoking the scripts.

**Where to look next (for extension or study)**

- **Spark Streaming consumer**: study the streaming pieces in the book/chapter code that subscribe to Kafka and call into the same model artifacts used by batch code — this demonstrates code reuse between batch and realtime.
- **Airflow**: if you want scheduled training, change `schedule_interval` in `resources/airflow/setup.py` and optionally add `email_on_failure` or `on_failure_callback` to `default_args`.
- **Metrics & monitoring**: add `on_failure_callback` or alerting integrations (Slack/email) to Airflow tasks, and add logging/metrics to Spark jobs for operational visibility.



