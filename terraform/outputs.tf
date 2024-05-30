output "cloudfront_distribution_id" {
  description = "The identifier for the distribution."
  value       = module.cloudfront.cloudfront_distribution_id
}

output "cloudfront_distribution_domain_name" {
  description = "The domain name corresponding to the distribution."
  value       = module.cloudfront.cloudfront_distribution_domain_name
}

output "alb_dns_name" {
  description = "The DNS name of the load balancer"
  value       = module.alb.dns_name
}

output "alb_arn_suffix" {
  description = "ARN suffix of the ALB"
  value       = module.alb.arn_suffix
}

output "target_group_arn_suffix" {
  description = "ARN suffix of the target group"
  value       = module.alb.target_groups["app_tg"].arn_suffix
}

output "autoscaling_group_name" {
  description = "The autoscaling group name"
  value       = module.asg.autoscaling_group_name
}

output "iam_role_name" {
  description = "The name of the IAM role"
  value       = module.asg.iam_role_name
}

output "launch_template_name" {
  description = "The name of the launch template"
  value       = module.asg.launch_template_name
}

output "launch_template_latest_version" {
  description = "The latest version of the launch template"
  value       = module.asg.launch_template_latest_version
}

output "launch_template_default_version" {
  description = "The default version of the launch template"
  value       = module.asg.launch_template_default_version
}
