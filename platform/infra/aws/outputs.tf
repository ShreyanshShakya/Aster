output "instance_id" {
  value = aws_instance.aster.id
}

output "instance_public_ip" {
  value = var.allocate_elastic_ip ? aws_eip.aster[0].public_ip : aws_instance.aster.public_ip
}

output "dashboard_url" {
  value = "http://${var.allocate_elastic_ip ? aws_eip.aster[0].public_ip : aws_instance.aster.public_ip}:3001"
}

output "ssm_start_session" {
  value = "aws ssm start-session --target ${aws_instance.aster.id} --region ${var.aws_region}"
}
