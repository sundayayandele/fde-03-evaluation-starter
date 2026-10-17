variable "region" {
  description = "AWS region. eu-west-1 (Ireland) or eu-central-1 (Frankfurt) keep data in the EU."
  type        = string
  default     = "eu-west-1"
}

variable "app_name" {
  description = "Name used for every resource."
  type        = string
  default     = "fde-03-evaluation"
}

variable "image_tag" {
  description = "Image tag pushed to the ECR repository created here."
  type        = string
  default     = "1.0.0"
}

variable "desired_count" {
  description = "Running tasks. Set to 0 to stop paying for compute between labs."
  type        = number
  default     = 1
}

variable "allowed_cidr" {
  description = "CIDR allowed to reach the service. Use your own IP (x.x.x.x/32) for labs."
  type        = string
  default     = "0.0.0.0/0"
}

variable "monthly_budget_usd" {
  description = "Monthly budget for this lab account; alerts at 50, 80 and 100 percent."
  type        = number
  default     = 50
}

variable "alert_email" {
  description = "Email that receives budget alerts."
  type        = string
}

variable "target_url" {
  description = "Base URL of the system under test (fde-02's service URL from its own Terraform output)."
  type        = string
  default     = "http://127.0.0.1:8001"
}
