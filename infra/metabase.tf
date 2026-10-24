# Read-only identity for Metabase: gold and silver only, no bronze, no writes to the lake.
# Its access key is created with the AWS CLI (see README), never by Terraform.

resource "aws_iam_user" "metabase" {
  name = "dc-bikeshare-metabase"
}

data "aws_iam_policy_document" "metabase" {
  statement {
    sid = "AthenaQueries"
    actions = [
      "athena:StartQueryExecution",
      "athena:StopQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:GetWorkGroup",
      "athena:ListQueryExecutions",
      "athena:GetDataCatalog",
      "athena:ListDataCatalogs",
      "athena:ListDatabases",
      "athena:GetDatabase",
      "athena:GetTableMetadata",
      "athena:ListTableMetadata",
    ]
    resources = [aws_athena_workgroup.bikeshare.arn]
  }

  statement {
    sid     = "GlueReadSilverAndGold"
    actions = ["glue:GetDatabase", "glue:GetDatabases", "glue:GetTable", "glue:GetTables", "glue:GetPartition", "glue:GetPartitions", "glue:BatchGetPartition"]
    resources = concat(
      ["arn:aws:glue:${var.region}:${local.account_id}:catalog"],
      [for name, db in aws_glue_catalog_database.layer : db.arn if contains(["silver", "gold"], name)],
      [for name, db in aws_glue_catalog_database.layer : "arn:aws:glue:${var.region}:${local.account_id}:table/${db.name}/*" if contains(["silver", "gold"], name)],
    )
  }

  statement {
    sid       = "ReadModelsOnly"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.lake.arn}/silver/*", "${aws_s3_bucket.lake.arn}/gold/*"]
  }

  statement {
    sid       = "ListLake"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.lake.arn]
  }

  # Athena writes query results here; Athena writes results at the workgroup output location; the lake data stays read-only.
  statement {
    sid       = "WriteOwnResults"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"]
    resources = ["${aws_s3_bucket.lake.arn}/athena-results/*"]
  }
}

resource "aws_iam_policy" "metabase" {
  name        = "dc-bikeshare-metabase-read"
  description = "Read-only access to silver and gold for the Metabase dashboard"
  policy      = data.aws_iam_policy_document.metabase.json
}

resource "aws_iam_user_policy_attachment" "metabase" {
  user       = aws_iam_user.metabase.name
  policy_arn = aws_iam_policy.metabase.arn
}

output "metabase_user" {
  description = "IAM user for the Metabase dashboard (read-only); create its access key with the AWS CLI."
  value       = aws_iam_user.metabase.name
}
