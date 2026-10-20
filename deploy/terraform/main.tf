# One EC2 instance (Ubuntu Pro 24.04 LTS) in the region's default VPC, with a fixed public IP.
# Docker, the portal and its database are then set up on it by ../ansible.

data "aws_vpc" "default" {
  default = true
}

# The latest Ubuntu Pro 24.04 LTS (Noble) image from Canonical
data "aws_ami" "ubuntu_pro" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu-pro-server/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-pro-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

resource "aws_key_pair" "deploy" {
  key_name   = "${var.name}-deploy"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "aws_security_group" "portal" {
  name        = "${var.name}-sg"
  description = "FutureLife portal: web on port 80, SSH from the allowed addresses only"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs
  }

  ingress {
    description = "Portal (HTTP)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.web_allowed_cidrs
  }

  egress {
    description = "Daftra, GitHub, Docker Hub, email, updates"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "portal" {
  ami                    = var.ami_id != "" ? var.ami_id : data.aws_ami.ubuntu_pro.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.deploy.key_name
  vpc_security_group_ids = [aws_security_group.portal.id]

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size
    encrypted             = true
    delete_on_termination = true
  }

  # Instance metadata only with a session token (IMDSv2)
  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  tags = {
    Name = var.name
  }

  lifecycle {
    # A newer Ubuntu image must not replace the running server (and its database)
    ignore_changes = [ami]
  }
}

# A fixed public address: the portal's URL, kept across stops and restarts
resource "aws_eip" "portal" {
  instance = aws_instance.portal.id
  domain   = "vpc"

  tags = {
    Name = var.name
  }
}

# The Ansible inventory for this server
resource "local_file" "ansible_inventory" {
  filename        = "${path.module}/../ansible/inventory.ini"
  file_permission = "0644"
  content         = <<-EOT
    [portal]
    ${aws_eip.portal.public_ip} ansible_user=ubuntu ansible_ssh_private_key_file=${pathexpand(var.ssh_private_key_path)}
  EOT
}
