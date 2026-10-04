resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/aws/lambda/dc-bikeshare-ingest"
  retention_in_days = 14
}

# Pin the function to the digest of the current :latest image, so a new
# `make image-push` followed by `terraform apply` deploys the new code.
data "aws_ecr_image" "ingest" {
  repository_name = aws_ecr_repository.ingest.name
  image_tag       = "latest"
}

resource "aws_lambda_function" "ingest" {
  function_name = "dc-bikeshare-ingest"
  description   = "Lands GBFS, trip and weather data in the S3 lake"
  role          = aws_iam_role.lambda_ingest.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.ingest.repository_url}@${data.aws_ecr_image.ingest.image_digest}"
  architectures = ["x86_64"]
  memory_size   = 2048
  timeout       = 300

  ephemeral_storage {
    size = 1024
  }

  environment {
    variables = {
      LAKE_BUCKET      = aws_s3_bucket.lake.bucket
      ALERTS_TOPIC_ARN = aws_sns_topic.alerts.arn
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.ingest,
    aws_iam_role_policy.lambda_ingest,
  ]
}

# Asynchronous invocations (Scheduler, Airflow): 2 retries, then the error alarm fires.
resource "aws_lambda_function_event_invoke_config" "ingest" {
  function_name                = aws_lambda_function.ingest.function_name
  maximum_retry_attempts       = 2
  maximum_event_age_in_seconds = 900
}
