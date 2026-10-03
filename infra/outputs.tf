output "lake_bucket" {
  description = "Name of the S3 lake bucket."
  value       = aws_s3_bucket.lake.bucket
}

output "athena_workgroup" {
  description = "Athena workgroup used by dbt and Metabase."
  value       = aws_athena_workgroup.bikeshare.name
}

output "athena_results_location" {
  description = "S3 location for Athena query results (dbt s3_staging_dir)."
  value       = "s3://${aws_s3_bucket.lake.bucket}/athena-results/"
}

output "glue_databases" {
  description = "Glue databases, one per layer."
  value       = [for db in aws_glue_catalog_database.layer : db.name]
}

output "alerts_topic_arn" {
  description = "SNS topic that receives every alert."
  value       = aws_sns_topic.alerts.arn
}
