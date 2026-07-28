variable "aws_region" {
  description = "AWS region for the temporary test deployment."
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  type    = string
  default = "aster-test"
}

variable "teardown_date" {
  description = "Human-readable date tag reminding the operator when to destroy this temporary stack."
  type        = string
}

variable "allowed_dashboard_cidr" {
  description = "Your current public IPv4 address in CIDR notation, for example 203.0.113.10/32."
  type        = string
}

variable "instance_type" {
  description = "CPU/RAM size for Docker, PostgreSQL, MinIO, and two CPU DMLF agent containers."
  type        = string
  default     = "t3.xlarge"
}

variable "root_volume_size_gb" {
  type    = number
  default = 50
}

variable "allocate_elastic_ip" {
  description = "Set true only when a stable public test URL is required."
  type        = bool
  default     = false
}

variable "budget_alert_email" {
  description = "Optional email for an 80% monthly test-budget alert. Leave blank to skip the Budget resource."
  type        = string
  default     = ""
}

variable "budget_limit_usd" {
  type    = number
  default = 15
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "public_subnet_cidr" {
  type    = string
  default = "10.42.1.0/24"
}

variable "availability_zone" {
  description = "Optional Mumbai AZ override. Leave blank to use the first available AZ."
  type        = string
  default     = ""
}
