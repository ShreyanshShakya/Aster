# Aster temporary AWS test host

This Terraform configuration creates a disposable, single-host test environment in Mumbai (`ap-south-1`). It provisions a new VPC, one public subnet, a restricted security group, an SSM-enabled Amazon Linux EC2 instance, encrypted root storage, and an optional budget alert.

It does **not** create RDS, ElastiCache, ALB, NAT Gateway, S3, GPU instances, or public SSH access. Do not use it for production.

## Prerequisites

- Terraform 1.6+
- AWS CLI authenticated to the intended AWS account
- Session Manager plugin for `aws ssm start-session`

## Deploy

```powershell
cd platform/infra/aws
Copy-Item terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set allowed_dashboard_cidr to your public IPv4 /32 and choose a teardown date.
terraform init
terraform plan
terraform apply
```

Copy the `ssm_start_session` output and run it to access the host without SSH. Once connected, clone or transfer this repository into `/opt/aster`, configure the platform environment file, and start the base Compose stack with the DMLF extension.

## Destroy

Export the test evidence first. Then run:

```powershell
terraform destroy
```

This terminates the EC2 instance and deletes the VPC resources it created. Its EBS root volume is configured to delete with the instance.
