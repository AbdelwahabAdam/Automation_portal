variable "name" {
  description = "Name given to every resource (and its Project tag)"
  type        = string
  default     = "futurelife-portal"
}

variable "region" {
  description = "AWS region (me-central-1 is the UAE)"
  type        = string
  default     = "me-central-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "m7i-flex.large"
}

variable "ami_id" {
  description = "AMI to use instead of the latest Ubuntu Pro 24.04 LTS found automatically (e.g. one subscribed to in the AWS Marketplace)"
  type        = string
  default     = ""
}

variable "root_volume_size" {
  description = "Size of the disk in GB (database, uploads, Docker images)"
  type        = number
  default     = 40
}

variable "ssh_public_key_path" {
  description = "Public half of the SSH key Ansible logs in with"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "ssh_private_key_path" {
  description = "Private half of that key; only written into the Ansible inventory"
  type        = string
  default     = "~/.ssh/id_ed25519"
}

variable "ssh_allowed_cidrs" {
  description = "Addresses allowed to SSH in, e.g. [\"203.0.113.7/32\"] for your office's public IP. Never 0.0.0.0/0 in production."
  type        = list(string)
}

variable "web_allowed_cidrs" {
  description = "Addresses allowed to open the portal (port 80)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
