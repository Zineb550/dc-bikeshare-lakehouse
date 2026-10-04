# Every 15 minutes on the clock (:00, :15, :30, :45 UTC), so slots line up with keys.
# The input is a literal string, not jsonencode(): jsonencode escapes < and >, which
# would stop the Scheduler from substituting the <aws.scheduler.scheduled-time> placeholder.
resource "aws_scheduler_schedule" "gbfs" {
  name                         = "dc-bikeshare-gbfs-15min"
  description                  = "Collect GBFS station status every 15 minutes"
  schedule_expression          = "cron(0/15 * * * ? *)"
  schedule_expression_timezone = "UTC"
  state                        = var.collection_enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.ingest.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = <<-EOT
      {"source": "gbfs", "mode": "scheduled", "scheduled_time": "<aws.scheduler.scheduled-time>"}
    EOT

    retry_policy {
      maximum_event_age_in_seconds = 900
      maximum_retry_attempts       = 2
    }
  }
}
