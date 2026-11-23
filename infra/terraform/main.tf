terraform {
  required_version = ">= 1.12.0"
  backend "oci" {}
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 7.0"
    }
  }
}

provider "oci" {
  region = var.region
}

variable "region" { type = string }
variable "compartment_id" { type = string }
variable "availability_domain" { type = string }
variable "ubuntu_image_id" { type = string }
variable "instance_shape" { type = string }
variable "ssh_cidr" { type = string }
variable "ssh_public_key" { type = string }
variable "ssh_host_public_key" { type = string }
variable "ssh_host_private_key" {
  type      = string
  sensitive = true
}

resource "oci_core_vcn" "notes" {
  compartment_id = var.compartment_id
  cidr_block     = "10.30.0.0/16"
  display_name   = "notas-vcn"
  dns_label      = "notas"
}

resource "oci_core_internet_gateway" "notes" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.notes.id
  display_name   = "notas-internet"
  enabled        = true
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.notes.id
  route_rules {
    network_entity_id = oci_core_internet_gateway.notes.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }
}

resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.notes.id
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }
  dynamic "ingress_security_rules" {
    for_each = { "22" = var.ssh_cidr, "80" = "0.0.0.0/0", "443" = "0.0.0.0/0" }
    content {
      protocol = "6"
      source   = ingress_security_rules.value
      tcp_options {
        min = tonumber(ingress_security_rules.key)
        max = tonumber(ingress_security_rules.key)
      }
    }
  }
}

resource "oci_core_subnet" "public" {
  compartment_id            = var.compartment_id
  vcn_id                    = oci_core_vcn.notes.id
  route_table_id            = oci_core_route_table.public.id
  security_list_ids         = [oci_core_security_list.public.id]
  cidr_block                = "10.30.1.0/24"
  display_name              = "notas-publica"
  dns_label                 = "publica"
  prohibit_public_ip_on_vnic = false
}

resource "oci_core_instance" "notes" {
  compartment_id      = var.compartment_id
  availability_domain = var.availability_domain
  display_name        = "notas-en-accion"
  shape               = var.instance_shape

  shape_config {
    ocpus         = 1
    memory_in_gbs = 2
  }

  source_details {
    source_type             = "image"
    source_id               = var.ubuntu_image_id
    boot_volume_size_in_gbs = 50
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode("#cloud-config\n${yamlencode({
      ssh_keys = {
        ed25519_private = var.ssh_host_private_key
        ed25519_public  = var.ssh_host_public_key
      }
    })}")
  }

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [metadata["user_data"]]
  }
}

output "public_ip" {
  value = oci_core_instance.notes.public_ip
}
