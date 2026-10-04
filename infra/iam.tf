# --- Lambda execution role: write to its three prefixes, publish alerts, write logs ---

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_ingest" {
  name               = "dc-bikeshare-lambda-ingest"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda_ingest" {
  statement {
    sid     = "WriteLakePrefixes"
    actions = ["s3:PutObject"]

    resources = [
      "${aws_s3_bucket.lake.arn}/bronze/*",
      "${aws_s3_bucket.lake.arn}/quarantine/*",
      "${aws_s3_bucket.lake.arn}/ops/run_log/*",
    ]
  }

  statement {
    sid       = "PublishAlerts"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }

  statement {
    sid       = "WriteLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.ingest.arn}:*"]
  }
}

resource "aws_iam_role_policy" "lambda_ingest" {
  name   = "ingest-least-privilege"
  role   = aws_iam_role.lambda_ingest.id
  policy = data.aws_iam_policy_document.lambda_ingest.json
}

# --- Scheduler role: may only invoke the ingest function ---

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "dc-bikeshare-scheduler-invoke"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler_invoke" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.ingest.arn]
  }
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name   = "invoke-ingest"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler_invoke.json
}
