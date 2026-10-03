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
