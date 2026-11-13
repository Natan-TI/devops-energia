# Infraestrutura do painel na AWS: uma máquina EC2 com endereço fixo e um grupo de segurança.
# Feito para caber nas restrições do AWS Academy Learner Lab (não é possível criar papéis de IAM).

terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
  # O estado fica em arquivo local, fora do repositório (veja .gitignore).
}

provider "aws" {
  region = var.regiao
  default_tags {
    tags = {
      Projeto    = "energia-que-da-lucro"
      Gerenciado = "terraform"
    }
  }
}

# Rede padrão da conta. O laboratório já vem com ela pronta.
data "aws_vpc" "padrao" {
  default = true
}

data "aws_subnets" "padrao" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.padrao.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# Imagem mais recente do Amazon Linux 2023, publicada pela própria AWS.
data "aws_ssm_parameter" "amazon_linux" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "painel" {
  name        = "energia-painel"
  description = "Painel do comerciante: so HTTP de entrada, sem SSH"
  vpc_id      = data.aws_vpc.padrao.id
}

# Única porta de entrada: o painel é um site público.
# Não existe regra para a porta 22: a administração é feita pelo AWS Systems Manager.
#trivy:ignore:AVD-AWS-0107 O painel é um site público; a única porta aberta é a 80.
resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.painel.id
  description       = "HTTP do painel"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

# Saída só por HTTPS e HTTP. HTTPS: baixar imagens e o código, e falar com o Systems Manager.
#trivy:ignore:AVD-AWS-0104 A máquina precisa alcançar repositórios públicos; a saída é limitada à porta 443.
resource "aws_vpc_security_group_egress_rule" "https" {
  security_group_id = aws_security_group.painel.id
  description       = "HTTPS de saida"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

# O build da imagem baixa pacotes do Debian, que são servidos por HTTP.
#trivy:ignore:AVD-AWS-0104 Necessário para os repositórios de pacotes; a saída é limitada à porta 80.
resource "aws_vpc_security_group_egress_rule" "http" {
  security_group_id = aws_security_group.painel.id
  description       = "HTTP de saida"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

# Token exigido em /metrics. Fica só no estado do Terraform (fora do repositório) e na máquina.
resource "random_password" "metrics_token" {
  length  = 40
  special = false
}

resource "aws_instance" "painel" {
  ami                    = data.aws_ssm_parameter.amazon_linux.value
  instance_type          = var.tipo_instancia
  subnet_id              = data.aws_subnets.padrao.ids[0]
  vpc_security_group_ids = [aws_security_group.painel.id]
  iam_instance_profile   = var.perfil_da_instancia

  user_data = templatefile("${path.module}/instalar.sh.tftpl", {
    repositorio   = var.repositorio
    versao        = var.versao
    metrics_token = random_password.metrics_token.result
  })
  user_data_replace_on_change = true

  # Só aceita o serviço de metadados com token (IMDSv2).
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = true
  }

  tags = {
    Name = "energia-painel"
  }

  lifecycle {
    # Uma imagem mais nova do Amazon Linux não deve recriar a máquina a cada "apply".
    ignore_changes = [ami]
  }
}

# Endereço fixo: a URL não muda quando o laboratório desliga e religa a máquina.
resource "aws_eip" "painel" {
  instance = aws_instance.painel.id
  domain   = "vpc"
  tags = {
    Name = "energia-painel"
  }
}
