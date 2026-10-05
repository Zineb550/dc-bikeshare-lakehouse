# Glue databases, one per layer. Bronze tables arrive in commit group 3;
# silver and gold tables are created by dbt.
resource "aws_glue_catalog_database" "layer" {
  for_each = toset(["bronze", "silver", "gold", "ops"])

  name         = each.key
  description  = "dc-bikeshare-lakehouse ${each.key} layer"
  location_uri = "s3://${aws_s3_bucket.lake.bucket}/${each.key}/"
}

# Dedicated workgroup: engine v3 (required for Iceberg MERGE), results in the lake
# bucket, and a hard per-query scan cap that cancels runaway queries.
resource "aws_athena_workgroup" "bikeshare" {
  name          = "bikeshare"
  description   = "dc-bikeshare-lakehouse queries (dbt, Metabase, ad hoc)"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.athena_scan_cap_bytes

    engine_version {
      selected_engine_version = "Athena engine version 3"
    }

    result_configuration {
      output_location = "s3://${aws_s3_bucket.lake.bucket}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}

# --- Bronze GBFS tables: raw JSON documents, one per line, gzipped ---
# Partition projection computes partitions from the path template, so no crawler
# or MSCK REPAIR is ever needed. One row = one fetched document.

locals {
  gbfs_projection = {
    "projection.enabled"          = "true"
    "projection.dt.type"          = "date"
    "projection.dt.format"        = "yyyy-MM-dd"
    "projection.dt.range"         = "2026-10-01,NOW"
    "projection.dt.interval"      = "1"
    "projection.dt.interval.unit" = "DAYS"
    "classification"              = "json"
  }

  gbfs_tables = {
    gbfs_station_status = {
      prefix = "bronze/gbfs/station_status"
      data   = "struct<stations:array<struct<station_id:string,num_bikes_available:int,num_ebikes_available:int,num_bikes_disabled:int,num_docks_available:int,num_docks_disabled:int,is_installed:int,is_renting:int,is_returning:int,last_reported:bigint>>>"
    }
    gbfs_station_information = {
      prefix = "bronze/gbfs/station_information"
      data   = "struct<stations:array<struct<station_id:string,short_name:string,name:string,lat:double,lon:double,capacity:int,region_id:string>>>"
    }
  }
}

resource "aws_glue_catalog_table" "gbfs" {
  for_each = local.gbfs_tables

  name          = each.key
  database_name = aws_glue_catalog_database.layer["bronze"].name
  description   = "Raw GBFS ${trimprefix(each.value.prefix, "bronze/gbfs/")} documents (one per slot)"
  table_type    = "EXTERNAL_TABLE"

  parameters = merge(local.gbfs_projection, {
    "storage.location.template" = "s3://${aws_s3_bucket.lake.bucket}/${each.value.prefix}/dt=$${dt}/"
  })

  partition_keys {
    name = "dt"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lake.bucket}/${each.value.prefix}/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
    }

    columns {
      name = "last_updated"
      type = "bigint"
    }

    columns {
      name = "ttl"
      type = "int"
    }

    columns {
      name = "version"
      type = "string"
    }

    columns {
      name = "data"
      type = each.value.data
    }
  }
}

# --- Bronze trips: monthly Parquet, every column a string, as published ---
locals {
  trip_columns = [
    "ride_id", "rideable_type", "started_at", "ended_at",
    "start_station_name", "start_station_id", "end_station_name", "end_station_id",
    "start_lat", "start_lng", "end_lat", "end_lng", "member_casual",
    "source_file", "source_etag",
  ]
}

resource "aws_glue_catalog_table" "trips" {
  name          = "trips"
  database_name = aws_glue_catalog_database.layer["bronze"].name
  description   = "Capital Bikeshare monthly trip files, all columns as published (strings)"
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "classification"                 = "parquet"
    "projection.enabled"             = "true"
    "projection.month.type"          = "date"
    "projection.month.format"        = "yyyy-MM"
    "projection.month.range"         = "2026-04,NOW"
    "projection.month.interval"      = "1"
    "projection.month.interval.unit" = "MONTHS"
    "storage.location.template"      = "s3://${aws_s3_bucket.lake.bucket}/bronze/trips/month=$${month}/"
  }

  partition_keys {
    name = "month"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lake.bucket}/bronze/trips/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    dynamic "columns" {
      for_each = local.trip_columns

      content {
        name = columns.value
        type = "string"
      }
    }
  }
}

# --- Bronze weather: one Open-Meteo response per run, plus ingest metadata ---
resource "aws_glue_catalog_table" "weather_raw" {
  name          = "weather_raw"
  database_name = aws_glue_catalog_database.layer["bronze"].name
  description   = "Raw Open-Meteo hourly responses (forecast and archive modes)"
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "classification"                      = "json"
    "projection.enabled"                  = "true"
    "projection.fetch_date.type"          = "date"
    "projection.fetch_date.format"        = "yyyy-MM-dd"
    "projection.fetch_date.range"         = "2026-03-01,NOW"
    "projection.fetch_date.interval"      = "1"
    "projection.fetch_date.interval.unit" = "DAYS"
    "storage.location.template"           = "s3://${aws_s3_bucket.lake.bucket}/bronze/weather/fetch_date=$${fetch_date}/"
  }

  partition_keys {
    name = "fetch_date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lake.bucket}/bronze/weather/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
    }

    columns {
      name = "latitude"
      type = "double"
    }

    columns {
      name = "longitude"
      type = "double"
    }

    columns {
      name = "timezone"
      type = "string"
    }

    columns {
      name = "hourly"
      type = "struct<time:array<string>,temperature_2m:array<double>,precipitation:array<double>,rain:array<double>,snowfall:array<double>,wind_speed_10m:array<double>,weather_code:array<int>>"
    }

    columns {
      name = "ingest_meta"
      type = "struct<mode:string,start_date:string,end_date:string,fetched_at:string>"
    }
  }
}

# --- ops.run_log: one JSON line per Lambda feed or Airflow task run ---
resource "aws_glue_catalog_table" "run_log" {
  name          = "run_log"
  database_name = aws_glue_catalog_database.layer["ops"].name
  description   = "Run metadata written by the ingest Lambda and the Airflow DAGs"
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "classification"              = "json"
    "projection.enabled"          = "true"
    "projection.dt.type"          = "date"
    "projection.dt.format"        = "yyyy-MM-dd"
    "projection.dt.range"         = "2026-10-01,NOW"
    "projection.dt.interval"      = "1"
    "projection.dt.interval.unit" = "DAYS"
    "storage.location.template"   = "s3://${aws_s3_bucket.lake.bucket}/ops/run_log/dt=$${dt}/"
  }

  partition_keys {
    name = "dt"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lake.bucket}/ops/run_log/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
    }

    dynamic "columns" {
      for_each = {
        run_id      = "string"
        source      = "string"
        mode        = "string"
        period      = "string"
        status      = "string"
        rows        = "bigint"
        bytes       = "bigint"
        object_key  = "string"
        duration_ms = "bigint"
        error       = "string"
        started_at  = "string"
      }

      content {
        name = columns.key
        type = columns.value
      }
    }
  }
}
