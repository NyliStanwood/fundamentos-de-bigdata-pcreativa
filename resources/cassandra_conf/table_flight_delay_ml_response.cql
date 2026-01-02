-- Cassandra schema for flight_delay_ml_response table
CREATE TABLE IF NOT EXISTS flight_delay_ml_response (
uuid UUID PRIMARY KEY,
origin text,
dayofweek int,
dayofmonth int,
dayofyear int,
dest text,
depdelay double,
timestamp text,
flightdate text,
carrier text,
distance double,
route text,
prediction double
);
