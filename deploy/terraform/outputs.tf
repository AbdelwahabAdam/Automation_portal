output "public_ip" {
  description = "The server's fixed address"
  value       = aws_eip.portal.public_ip
}

output "portal_url" {
  description = "Where the portal opens once Ansible has run"
  value       = "http://${aws_eip.portal.public_ip}"
}

output "ssh" {
  description = "Log in to the server"
  value       = "ssh -i ${var.ssh_private_key_path} ubuntu@${aws_eip.portal.public_ip}"
}

output "ami" {
  description = "The image the server was created from"
  value       = aws_instance.portal.ami
}
