variable "regiao" {
  description = "Região da AWS. O Learner Lab só permite us-east-1 e us-west-2."
  type        = string
  default     = "us-east-1"
}

variable "tipo_instancia" {
  description = "Tamanho da máquina. A t3.small (2 GB) comporta o banco, a API e o build da imagem."
  type        = string
  default     = "t3.small"
}

variable "perfil_da_instancia" {
  description = "Perfil de IAM da máquina. No Learner Lab, o LabInstanceProfile já existe e dá acesso ao Systems Manager."
  type        = string
  default     = "LabInstanceProfile"
}

variable "repositorio" {
  description = "Endereço HTTPS do repositório público com o código do painel."
  type        = string
  default     = "https://github.com/Natan-TI/devops-energia.git"
}

variable "versao" {
  description = "Branch, etiqueta ou commit instalado na criação da máquina. Depois disso, o pipeline cuida do deploy."
  type        = string
  default     = "main"
}
