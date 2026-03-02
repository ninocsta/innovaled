from django import forms
from django.forms import inlineformset_factory
from .models import Cliente, Contrato, Video, Banco, Vendedor, Local, FormaPagamento, DocumentoContrato, Registro
import re
import unicodedata


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["razao_social", "cpf_cnpj", "email", "telefone", "telefone_financeiro", "email_financeiro"]
        widgets = {
            'razao_social': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone_financeiro': forms.TextInput(attrs={'class': 'form-control'}),
            'email_financeiro': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class VideoForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = ["tempo_video", "local"]
        widgets = {
            'tempo_video': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 00:03:25'}),
            'local': forms.Select(attrs={'class': 'form-select'}),
        }
        error_messages = {
            'local': {
                'required': 'Campo obrigatório.',
            },
        }

        
VideoFormSet = inlineformset_factory(
    Contrato,
    Video,
    form=VideoForm,
    extra=1,           # começa com 1 formulário vazio
    can_delete=True    # permite remover vídeos
)


class ContratoForm(forms.ModelForm):
    vendedor = forms.ModelChoiceField(
        queryset=Vendedor.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select', 'required': True})
    )
    banco = forms.ModelChoiceField(
        queryset=Banco.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    forma_pagamento = forms.ModelChoiceField(
        queryset=FormaPagamento.objects.all(),
        widget=forms.RadioSelect(attrs={'class': 'form-check-input', 'required': True})
    )

    class Meta:
        model = Contrato
        exclude = [
            'created_by', 'updated_by',
            'cliente', 'status', 'cobranca_gerada',
            'video', 'data_cancelamento_contrato'
        ]
        widgets = {
            'vigencia_meses': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'valor_mensalidade': forms.NumberInput(attrs={'class': 'form-control'}),
            'primeiro_pagamento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'segundo_pagamento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_assinatura': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'data_vencimento_primeira_parcela': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'data_ultima_parcela': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'link_cobranca': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'link_notas': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        }
        labels = {
            'vigencia_meses': 'Vigência (em meses)',
            'valor_mensalidade': 'Valor da Mensalidade',
            'primeiro_pagamento': 'Primeiro Pagamento',
            'segundo_pagamento': 'Segundo Pagamento',
            'data_assinatura': 'Data da Assinatura',
            'data_vencimento_primeira_parcela': 'Vencimento da Primeira Parcela',
            'data_ultima_parcela': 'Data da Última Parcela',
            'observacoes': 'Observações',
            'link_cobranca': 'Link de Cobrança',
            'link_notas': 'Link de Notas',
        }


class PagamentoForm(forms.ModelForm):
    class Meta:
        model = Contrato
        fields = ["primeiro_pagamento", "segundo_pagamento"]
        widgets = {
            "primeiro_pagamento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "segundo_pagamento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

class DocumentoContratoForm(forms.ModelForm):
    class Meta:
        model = DocumentoContrato
        fields = ["arquivo", "descricao"]
        widgets = {
            "arquivo": forms.FileInput(attrs={"class": "form-control"}),
            "descricao": forms.TextInput(attrs={"class": "form-control"}),
        }


class ContratoRegistroForm(forms.ModelForm):
    class Meta:
        model = Registro
        fields = ['data_hora', 'observacao']
        widgets = {
            'data_hora': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',  # Formato para datetime-local
                attrs={
                    'class': 'form-control',
                    'type': 'datetime-local'  # Usa datetime-local para incluir a hora
                }
            ),
            'observacao': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 3,
                    'placeholder': 'Digite as observações aqui...',
                }
            ),
        }
        labels = {
            'data_hora': 'Data do Registro',
            'observacao': 'Observações',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'