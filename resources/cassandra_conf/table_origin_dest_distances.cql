
CREATE TABLE IF NOT EXISTS origin_dest_distances (
    origin text,
    dest text,
    distance double,
    PRIMARY KEY ((origin, dest))
) WITH comment = 'Airport pair distances for route calculations';
