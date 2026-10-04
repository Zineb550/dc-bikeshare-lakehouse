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
