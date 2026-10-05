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

# --- Airflow / dbt identity (local Airflow on the laptop) ---
# The access key is created with the AWS CLI, not Terraform, so the secret never
# lands in the Terraform state file.

resource "aws_iam_user" "airflow" {
  name = "dc-bikeshare-airflow"
}

data "aws_iam_policy_document" "airflow" {
  statement {
    sid       = "InvokeIngest"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.ingest.arn]
  }

  statement {
    sid       = "PublishAlerts"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }

  statement {
    sid = "AthenaWorkgroup"
    actions = [
      "athena:StartQueryExecution",
      "athena:StopQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:GetWorkGroup",
      "athena:ListQueryExecutions",
    ]
    resources = [aws_athena_workgroup.bikeshare.arn]
  }

  statement {
    sid = "AthenaCatalog"
    actions = [
      "athena:GetDataCatalog",
      "athena:ListDataCatalogs",
      "athena:ListDatabases",
      "athena:GetDatabase",
      "athena:GetTableMetadata",
      "athena:ListTableMetadata",
    ]
    resources = ["arn:aws:athena:${var.region}:${local.account_id}:datacatalog/AwsDataCatalog"]
  }

  statement {
    sid = "GlueCatalog"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:BatchGetPartition",
      "glue:CreateTable",
      "glue:UpdateTable",
      "glue:DeleteTable",
      "glue:BatchDeleteTable",
      "glue:GetTableVersions",
      "glue:DeleteTableVersion",
      "glue:BatchDeleteTableVersion",
      "glue:CreatePartition",
      "glue:BatchCreatePartition",
      "glue:UpdatePartition",
      "glue:DeletePartition",
      "glue:BatchDeletePartition",
    ]
    resources = concat(
      ["arn:aws:glue:${var.region}:${local.account_id}:catalog"],
      [for db in aws_glue_catalog_database.layer : db.arn],
      [for db in aws_glue_catalog_database.layer : "arn:aws:glue:${var.region}:${local.account_id}:table/${db.name}/*"],
    )
  }

  statement {
    sid       = "LakeBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.lake.arn]
  }

  statement {
    sid       = "ReadBronze"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.lake.arn}/bronze/*"]
  }

  statement {
    sid = "WriteModelsAndResults"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
    ]
    resources = [
      "${aws_s3_bucket.lake.arn}/silver/*",
      "${aws_s3_bucket.lake.arn}/gold/*",
      "${aws_s3_bucket.lake.arn}/ops/*",
      "${aws_s3_bucket.lake.arn}/athena-results/*",
    ]
  }
}


# Managed policy, not inline: inline user policies are capped at 2,048 characters.
resource "aws_iam_policy" "airflow" {
  name        = "dc-bikeshare-airflow-dbt"
  description = "Least-privilege access for local Airflow and dbt"
  policy      = data.aws_iam_policy_document.airflow.json
}

resource "aws_iam_user_policy_attachment" "airflow" {
  user       = aws_iam_user.airflow.name
  policy_arn = aws_iam_policy.airflow.arn
}
