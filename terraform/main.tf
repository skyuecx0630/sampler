provider "aws" {
  default_tags {
    tags = {
      "project" = "skills"
      "owner"   = "hmoon"
    }
  }
}


data "aws_availability_zones" "available" {
  state = "available"
}


data "aws_ec2_managed_prefix_list" "cloudfront_pl" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}


locals {
  # VPC
  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  vpc_name = "${var.resource_name_tag_perfix}-vpc"
  vpc_cidr = var.vpc_cidr

  public_subnets      = [for k, v in local.azs : cidrsubnet(var.vpc_cidr, 4, k)]
  public_subnet_names = [for k, v in local.azs : "${var.resource_name_tag_perfix}-public-subnet-${v}"]

  # ALB
  alb_name              = "${var.resource_name_tag_perfix}-app-alb"
  alb_sg_name           = "${var.resource_name_tag_perfix}-alb-sg"
  app_tg_name           = "${var.resource_name_tag_perfix}-app-tg"
  app_health_check_path = var.app_health_check_path

  # App
  asg_name                 = "${var.resource_name_tag_perfix}-app-asg"
  app_launch_template_name = "${var.resource_name_tag_perfix}-app-lt"
  app_port                 = var.app_port

  app_ami_id        = var.app_ami_id
  app_instance_type = var.app_instance_type
  app_iam_role_name = "${var.resource_name_tag_perfix}-app-role"
  app_sg_name       = "${var.resource_name_tag_perfix}-app-sg"
}


module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = local.vpc_name
  cidr = local.vpc_cidr

  azs                 = local.azs
  public_subnets      = local.public_subnets
  public_subnet_names = local.public_subnet_names

  create_igw           = true
  enable_dns_hostnames = true
}


module "alb_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.1"

  name        = local.alb_sg_name
  description = local.alb_sg_name
  vpc_id      = module.vpc.vpc_id

  ingress_prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront_pl.id]
  ingress_rules           = ["http-80-tcp"]
  egress_rules            = ["all-all"]
}


module "app_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.1"

  name        = local.app_sg_name
  description = local.app_sg_name
  vpc_id      = module.vpc.vpc_id

  computed_ingress_with_source_security_group_id = [
    {
      from_port                = local.app_port
      to_port                  = local.app_port
      protocol                 = "tcp"
      source_security_group_id = module.alb_sg.security_group_id
    }
  ]
  egress_rules = ["all-all"]

  number_of_computed_ingress_with_source_security_group_id = 1
}


module "alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "~> 9.9"

  name                       = local.alb_name
  enable_deletion_protection = false

  vpc_id                = module.vpc.vpc_id
  subnets               = module.vpc.public_subnets
  create_security_group = false
  security_groups       = [module.alb_sg.security_group_id]

  listeners = {
    http = {
      port     = 80
      protocol = "HTTP"

      forward = {
        target_group_key = "app_tg"
      }
    }
  }

  target_groups = {
    app_tg = {
      name                 = local.app_tg_name
      protocol             = "HTTP"
      port                 = local.app_port
      target_type          = "instance"
      deregistration_delay = 30
      create_attachment    = false

      health_check = {
        path     = local.app_health_check_path
        protocol = "HTTP"
        port     = local.app_port
        matcher  = "200"
      }
    }
  }
}


module "cloudfront" {
  source  = "terraform-aws-modules/cloudfront/aws"
  version = "~> 3.4"

  enabled = true

  origin = {
    alb = {
      domain_name = module.alb.dns_name
      origin_id   = "alb"

      custom_origin_config = {
        http_port              = 80
        https_port             = 443
        origin_protocol_policy = "http-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }
    }
  }

  default_cache_behavior = {
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    viewer_protocol_policy = "redirect-to-https"
    target_origin_id       = "alb"

    # Cache policy: CachingDisabled
    use_forwarded_values = false
    cache_policy_id      = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
  }
}

module "asg" {
  source  = "terraform-aws-modules/autoscaling/aws"
  version = "~> 7.5"

  name                = local.asg_name
  min_size            = 1
  max_size            = 4
  desired_capacity    = 1
  capacity_rebalance  = true
  vpc_zone_identifier = module.vpc.public_subnets

  create_traffic_source_attachment = true
  traffic_source_type              = "elbv2"
  traffic_source_identifier        = module.alb.target_groups["app_tg"].arn

  launch_template_name = local.app_launch_template_name

  instance_refresh = {
    strategy = "Rolling"
    preferences = {
      min_healthy_percentage = 100
      max_healthy_percentage = 200
      skip_matching          = true
    }
    triggers = ["launch_template"]
  }

  image_id          = local.app_ami_id
  instance_type     = local.app_instance_type
  enable_monitoring = true

  create_iam_instance_profile = true
  iam_role_name               = local.app_iam_role_name
  iam_role_policies = {
    AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  block_device_mappings = [
    {
      # Root volume
      device_name = "/dev/xvda"
      no_device   = 0
      ebs = {
        delete_on_termination = true
        encrypted             = true
        volume_size           = 20
        volume_type           = "gp3"
      }
    }
  ]

  network_interfaces = [
    {
      delete_on_termination = true
      device_index          = 0
      security_groups       = [module.app_sg.security_group_id]
    }
  ]

  metadata_options = {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
}
