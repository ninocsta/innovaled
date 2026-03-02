from django.db import models
from django.contrib.auth.models import User
import datetime
import os
import re
import unicodedata


class BaseAudit(models.Model):
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="%(class)s_created",
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
        null=True, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Cliente(BaseAudit):
    razao_social = models.CharField(max_length=255)
    cpf_cnpj = models.CharField(max_length=20)
    email = models.EmailField()
    telefone = models.CharField(max_length=20, blank=True, null=True)
    telefone_financeiro = models.CharField(max_length=20, blank=True, null=True)
    email_financeiro = models.EmailField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # Normalizar razão social (sem acentos e maiúscula)
        if self.razao_social:
            self.razao_social = unicodedata.normalize("NFKD", self.razao_social).encode("ASCII", "ignore").decode("utf-8")
            self.razao_social = self.razao_social.upper().strip()

        # Remover caracteres não numéricos dos campos de números
        if self.cpf_cnpj:
            self.cpf_cnpj = re.sub(r"\D", "", self.cpf_cnpj)

        if self.telefone:
            self.telefone = re.sub(r"\D", "", self.telefone)

        if self.telefone_financeiro:
            self.telefone_financeiro = re.sub(r"\D", "", self.telefone_financeiro)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.razao_social} ({self.cpf_cnpj})"

    class Meta:
        verbose_name_plural = 'Clientes'
        ordering = ['razao_social']


class Banco(BaseAudit):
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome


class Vendedor(BaseAudit):
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name_plural = 'Vendedores'


class Local(BaseAudit):
    nome = models.CharField(max_length=255)

    def __str__(self):
        return self.nome
    
    class Meta:
        verbose_name_plural = 'Locais'





class FormaPagamento(BaseAudit):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Forma de Pagamento"
        verbose_name_plural = "Formas de Pagamento"

class StatusContrato(BaseAudit):
    nome_status = models.CharField(max_length=100)

    def __str__(self):
        return self.nome_status
    
    class Meta:
        verbose_name = "Status do Contrato"
        verbose_name_plural = "Status dos Contratos"


def contrato_upload_path(instance, filename):
    # organiza uploads por contrato e tipo de documento
    return os.path.join(
        "contratos",
        f"contrato_{instance.contrato.id_contrato}",
        filename
    )

class Contrato(BaseAudit):
    id_contrato = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="contratos")

    primeiro_pagamento = models.DateField(blank=True, null=True)
    segundo_pagamento = models.DateField(blank=True, null=True)

    banco = models.ForeignKey(Banco, on_delete=models.SET_NULL, null=True, blank=True)
    cobranca_gerada = models.BooleanField(default=False)

    vendedor = models.ForeignKey(Vendedor, on_delete=models.SET_NULL, null=True, blank=True)
    vigencia_meses = models.IntegerField(default=12)


    valor_mensalidade = models.DecimalField(max_digits=10, decimal_places=2)


    data_assinatura = models.DateField(default=datetime.date.today)
    data_vencimento_contrato = models.DateField(blank=True, null=True)
    data_cancelamento_contrato = models.DateField(blank=True, null=True)
    data_vencimento_primeira_parcela = models.DateField(blank=True, null=True)
    data_ultima_parcela = models.DateField(blank=True, null=True)

    forma_pagamento = models.ForeignKey(FormaPagamento, on_delete=models.SET_NULL, null=True, blank=True)
    observacoes = models.TextField(blank=True, null=True)

    link_cobranca = models.URLField(max_length=500, blank=True, null=True, verbose_name="Link de Cobrança")
    link_notas = models.URLField(max_length=500, blank=True, null=True, verbose_name="Link de Notas")

    status = models.ForeignKey(StatusContrato, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Contrato {self.id_contrato:05d} - {self.cliente.razao_social}"

    @property
    def valor_total(self):
        """Calcula dinamicamente o valor total do contrato"""
        if self.valor_mensalidade and self.vigencia_meses:
            return self.valor_mensalidade * self.vigencia_meses
        return 0
    

    class Meta:
        ordering = ["-data_assinatura", "-id_contrato"]


class DocumentoContrato(BaseAudit):
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name="documentos")
    arquivo = models.FileField(upload_to=contrato_upload_path)
    descricao = models.CharField(max_length=255, blank=True, null=True)

    @property
    def filename(self):
        return os.path.basename(self.arquivo.name)

    def __str__(self):
        return f"{self.contrato} - {self.descricao or self.arquivo.name}"

    def delete(self, *args, **kwargs):
        # Excluir o arquivo do storage antes de remover o registro
        if self.arquivo and self.arquivo.storage.exists(self.arquivo.name):
            self.arquivo.delete(save=False)
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = "Documento do Contrato"
        verbose_name_plural = "Documentos do Contrato"

class Registro(BaseAudit):
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name="registros")
    data_hora = models.DateTimeField(default=datetime.datetime.now)
    observacao = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Registro {self.id:05d} - {self.contrato}"
    

class Video(BaseAudit):
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name="videos")
    tempo_video = models.DurationField(default=10)  
    local = models.ForeignKey(Local, on_delete=models.CASCADE)
    status = models.BooleanField(default=False)
    data_subiu = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Vídeo {self.id} - {self.tempo_video}"