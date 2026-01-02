package es.upm.dit.ging.predictor
// import com.mongodb.spark._
import org.apache.spark.ml.classification.RandomForestClassificationModel
import org.apache.spark.ml.feature.{Bucketizer, StringIndexerModel, VectorAssembler}
import org.apache.spark.sql.functions.{concat, from_json, lit, to_json, struct, col}
import org.apache.spark.sql.types.{DataTypes, StructType}
import org.apache.spark.sql.{DataFrame, SparkSession}
import com.datastax.spark.connector._
import com.datastax.spark.connector.cql.CassandraConnector


object MakePrediction {

  def main(args: Array[String]): Unit = {
    println("\n" + "="*80)
    println("*** FLIGHT DELAY PREDICTION ENGINE STARTING ***")
    println("="*80 + "\n")

    val spark = SparkSession
      .builder
      .appName("StructuredNetworkWordCount")
      // .master("local[*]")
      .getOrCreate()
    import spark.implicits._

    println(">>> Loading ML models and configurations...")
    
    //Load the arrival delay bucketizer
    // val base_path= "/home/ibdn/practica_creativa"
    val base_path= "/practica_creativa"
    val arrivalBucketizerPath = "%s/models/arrival_bucketizer_2.0.bin".format(base_path)
    print(arrivalBucketizerPath.toString())
    val arrivalBucketizer = Bucketizer.load(arrivalBucketizerPath)
    val columns= Seq("Carrier","Origin","Dest","Route")

    //Load all the string field vectorizer pipelines into a dict
    val stringIndexerModelPath =  columns.map(n=> ("%s/models/string_indexer_model_"
      .format(base_path)+"%s.bin".format(n)).toSeq)
    val stringIndexerModel = stringIndexerModelPath.map{n => StringIndexerModel.load(n.toString)}
    val stringIndexerModels  = (columns zip stringIndexerModel).toMap

    // Load the numeric vector assembler
    val vectorAssemblerPath = "%s/models/numeric_vector_assembler.bin".format(base_path)
    val vectorAssembler = VectorAssembler.load(vectorAssemblerPath)

    // Load the classifier model
    val randomForestModelPath = "%s/models/spark_random_forest_classifier.flight_delays.5.0.bin".format(
      base_path)
    val rfc = RandomForestClassificationModel.load(randomForestModelPath)

    println("✓ ML Models loaded successfully\n")
    println(">>> Starting Kafka consumer for flight-delay-ml-request topic...")

    //Process Prediction Requests in Streaming
    val df = spark
      .readStream
      .format("kafka")
      .option("kafka.bootstrap.servers", "kafka:9092")
      .option("subscribe", "flight-delay-ml-request")
      .load()
    df.printSchema()

    val flightJsonDf = df.selectExpr("CAST(value AS STRING)")

    val struct = new StructType()
      .add("Origin", DataTypes.StringType)
      .add("FlightNum", DataTypes.StringType)
      .add("DayOfWeek", DataTypes.IntegerType)
      .add("DayOfYear", DataTypes.IntegerType)
      .add("DayOfMonth", DataTypes.IntegerType)
      .add("Dest", DataTypes.StringType)
      .add("DepDelay", DataTypes.DoubleType)
      .add("Prediction", DataTypes.StringType)
      .add("Timestamp", DataTypes.TimestampType)
      .add("FlightDate", DataTypes.DateType)
      .add("Carrier", DataTypes.StringType)
      .add("UUID", DataTypes.StringType)
      .add("Distance", DataTypes.DoubleType)
      .add("Carrier_index", DataTypes.DoubleType)
      .add("Origin_index", DataTypes.DoubleType)
      .add("Dest_index", DataTypes.DoubleType)
      .add("Route_index", DataTypes.DoubleType)

    val flightNestedDf = flightJsonDf.select(from_json($"value", struct).as("flight"))
    flightNestedDf.printSchema()

    // DataFrame for Vectorizing string fields with the corresponding pipeline for that column
    val flightFlattenedDf = flightNestedDf.selectExpr("flight.Origin",
      "flight.DayOfWeek","flight.DayOfYear","flight.DayOfMonth","flight.Dest",
      "flight.DepDelay","flight.Timestamp","flight.FlightDate",
      "flight.Carrier","flight.UUID","flight.Distance")
    flightFlattenedDf.printSchema()

    val predictionRequestsWithRouteMod = flightFlattenedDf.withColumn(
      "Route",
                concat(
                  flightFlattenedDf("Origin"),
                  lit('-'),
                  flightFlattenedDf("Dest")
                )
    )

    // Dataframe for Vectorizing numeric columns
    val flightFlattenedDf2 = flightNestedDf.selectExpr("flight.Origin",
      "flight.DayOfWeek","flight.DayOfYear","flight.DayOfMonth","flight.Dest",
      "flight.DepDelay","flight.Timestamp","flight.FlightDate",
      "flight.Carrier","flight.UUID","flight.Distance",
      "flight.Carrier_index","flight.Origin_index","flight.Dest_index","flight.Route_index")
    flightFlattenedDf2.printSchema()

    val predictionRequestsWithRouteMod2 = flightFlattenedDf2.withColumn(
      "Route",
      concat(
        flightFlattenedDf2("Origin"),
        lit('-'),
        flightFlattenedDf2("Dest")
      )
    )

    // Vectorize string fields with the corresponding pipeline for that column
    // Turn category fields into categoric feature vectors, then drop intermediate fields
    val predictionRequestsWithRoute = stringIndexerModel.map(n=>n.transform(predictionRequestsWithRouteMod))

    //Vectorize numeric columns: DepDelay, Distance and index columns
    val vectorizedFeatures = vectorAssembler.setHandleInvalid("keep").transform(predictionRequestsWithRouteMod2)

    // Inspect the vectors
    vectorizedFeatures.printSchema()

    // Drop the individual index columns
    val finalVectorizedFeatures = vectorizedFeatures
        .drop("Carrier_index")
        .drop("Origin_index")
        .drop("Dest_index")
        .drop("Route_index")

    // Inspect the finalized features
    finalVectorizedFeatures.printSchema()

    // Make the prediction
    val predictions = rfc.transform(finalVectorizedFeatures)
      .drop("Features_vec")

    // Drop the features vector and prediction metadata to give the original fields
    val finalPredictions = predictions.drop("indices").drop("values").drop("rawPrediction").drop("probability")

    // Inspect the output
    finalPredictions.printSchema()

    println("\n" + "="*80)
    println("*** INITIATING OUTPUT STREAMS ***")
    println("="*80 + "\n")

    println(">>> Configuring Cassandra output stream...")

    // Map DataFrame columns to match Cassandra schema (lowercase)
    val cassandraMappedDF = finalPredictions.select(
      col("UUID").as("uuid"),
      col("Origin").as("origin"),
      col("DayOfWeek").as("dayofweek"),
      col("DayOfMonth").as("dayofmonth"),
      col("DayOfYear").as("dayofyear"),
      col("Dest").as("dest"),
      col("DepDelay").as("depdelay"),
      col("Timestamp").cast("string").as("timestamp"),
      col("FlightDate").cast("string").as("flightdate"),
      col("Carrier").as("carrier"),
      col("Distance").as("distance"),
      col("Route").as("route"),
      col("Prediction").as("prediction")
    )

    // 2. Define the streaming query for Cassandra
    val query = cassandraMappedDF
      .writeStream
      .format("org.apache.spark.sql.cassandra")
      .option("keyspace", "agile_data_science")
      .option("table", "flight_delay_ml_response")
      .option("checkpointLocation", "/tmp/cassandra_checkpoint")
      // Connection deets
      .option("spark.cassandra.connection.host", "cassandra")
      .option("spark.cassandra.connection.port", "9042")
      .option("spark.cassandra.auth.username", "cassandra")
      .option("spark.cassandra.auth.password", "cassandra")
      .outputMode("append")
      .start()

    println("✓✓✓ PREDICTIONS NOW SAVED TO CASSANDRA ✓✓✓\n")

    // // define a streaming query for MongoDB
    // println(">>> Configuring MongoDB output stream...")
    // val dataStreamWriter = finalPredictions
    //   .writeStream
    //   .format("mongodb")
    //   .option("spark.mongodb.connection.uri", "mongodb://root:example@mongo:27017/agile_data_science?authSource=admin")
    //   .option("spark.mongodb.database", "agile_data_science")
    //   .option("checkpointLocation", "/tmp")
    //   .option("spark.mongodb.collection", "flight_delay_ml_response")
    //   .outputMode("append")
    
    // // run the MongoDB query
    // println(">>> STARTING MONGODB WRITE STREAM...")
    // val query = dataStreamWriter.start()
    // println("✓✓✓ PREDICTIONS NOW POSTED TO MONGODB ✓✓✓\n")

    // Write predictions to Kafka topic
    println(">>> Configuring Kafka output stream...")
    val kafkaOutput = finalPredictions.selectExpr("to_json(struct(*)) as value")
    val kafkaStreamWriter = kafkaOutput
      .writeStream
      .format("kafka")
      .option("kafka.bootstrap.servers", "kafka:9092")
      .option("topic", "flight-delay-ml-response")
      .option("checkpointLocation", "/tmp/kafka_checkpoint")
      .outputMode("append")
    
    // run the Kafka query
    println(">>> STARTING KAFKA WRITE STREAM...")
    val kafkaQuery = kafkaStreamWriter.start()
    println("✓✓✓ PREDICTIONS NOW POSTED TO KAFKA TOPIC 'flight-delay-ml-response' ✓✓✓\n")
    
    
    // Console Output for predictions
    println(">>> Configuring console output stream...")

    val consoleOutput = finalPredictions.writeStream
      .outputMode("append")
      .format("console")
      .start()
    
    println("\n" + "="*80)
    println("*** ALL STREAMS ACTIVE - ENGINE READY FOR PREDICTIONS ***")
    println("*** Listening for requests on: flight-delay-ml-request ***")
    println("*** Sending results to: MongoDB + Kafka (flight-delay-ml-response) ***")
    println("="*80 + "\n")
    
    consoleOutput.awaitTermination()
  }

}
