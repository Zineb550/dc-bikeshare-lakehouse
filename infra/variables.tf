variable "region" {
  description = "AWS region for every resource."
  type        = string
  default     = "us-east-1"
}

variable "alert_email" {
  description = "Email address that receives SNS alerts and budget notifications."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly cost budget that triggers email notifications."
  type        = number
  default     = 5
}

variable "athena_scan_cap_bytes" {
  description = "Per-query bytes-scanned limit enforced by the Athena workgroup (minimum 10 MB)."
  type        = number
  default     = 1073741824 # 1 GB
}
