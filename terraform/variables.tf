variable "resource_name_tag_perfix" {
  type        = string
  description = "Prefix for resource name tag"
  default     = "skills"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR for VPC"
  default     = "10.100.0.0/16"
}

variable "app_ami_id" {
  type        = string
  description = "AMI ID for app instances"
  default     = "ami-05e7cd38ae962ebc9"
}

variable "app_instance_type" {
  type        = string
  description = "Instance type for app instances"
  default     = "t3.medium"
}

variable "app_port" {
  type        = number
  description = "Port for app instances"
  default     = 8080
}

variable "app_health_check_path" {
  type        = string
  description = "Health check path for app instances"
  default     = "/dummy/health"
}
