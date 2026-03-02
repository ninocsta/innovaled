from django.shortcuts import render
from django.core.paginator import Paginator
from .models import Contrato, Vendedor, Local, Cliente, StatusContrato, DocumentoContrato, Video, Registro
from .forms import ClienteForm, ContratoForm, DocumentoContratoForm, VideoFormSet, VideoForm, ContratoRegistroForm
from django.contrib import messages
from django.shortcuts import redirect
from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta
from django.db.models import Q, Count
from core.services import dashboard as dashboard_service
from django.http import HttpResponse
import pandas as pd
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.views.decorators.http import require_POST


@login_required
def contrato_list(request):
    # 🔍 Filtros
    query_nome = request.GET.get("nome", "").strip()
    query_cnpj = request.GET.get("cnpj", "").strip()
    query_vendedor = request.GET.get("vendedor", "").strip()
    query_data_inicio = request.GET.get("data_inicio", "").strip()
    query_data_fim = request.GET.get("data_fim", "").strip()
    query_local = request.GET.get("local", "").strip()

    # 📄 Itens por página (com fallback seguro)
    try:
        itens_por_pagina = int(request.GET.get("itens", 10))
        if itens_por_pagina <= 0:
            itens_por_pagina = 10
    except ValueError:
        itens_por_pagina = 10

    # 🔄 Consulta principal
    contratos = (
        Contrato.objects
        .select_related("cliente", "vendedor", "status")   # FK/OneToOne
        .prefetch_related("videos__local")                 # ManyToMany / OneToMany
        .all()
    )

    # Aplicando filtros
    if query_nome:
        contratos = contratos.filter(cliente__razao_social__icontains=query_nome)
    if query_cnpj:
        contratos = contratos.filter(cliente__cpf_cnpj__icontains=query_cnpj)
    if query_vendedor:
        contratos = contratos.filter(vendedor_id=query_vendedor)
    if query_local:
        contratos = contratos.filter(videos__local_id=query_local).distinct()

    # Datas com validação
    if query_data_inicio:
        try:
            data_inicio = datetime.strptime(query_data_inicio, "%Y-%m-%d").date()
            contratos = contratos.filter(data_assinatura__gte=data_inicio)
        except ValueError:
            pass
    if query_data_fim:
        try:
            data_fim = datetime.strptime(query_data_fim, "%Y-%m-%d").date()
            contratos = contratos.filter(data_assinatura__lte=data_fim)
        except ValueError:
            pass

    # 🔄 Paginação
    paginator = Paginator(contratos, itens_por_pagina)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # 🔗 Preservando querystring (sem o parâmetro "page")
    params = request.GET.copy()
    params.pop("page", None)
    extra_query = "&" + params.urlencode() if params else ""

    context = {
        "page_obj": page_obj,
        "query_nome": query_nome,
        "query_cnpj": query_cnpj,
        "query_vendedor": query_vendedor,
        "query_data_inicio": query_data_inicio,
        "query_data_fim": query_data_fim,
        "query_local": query_local,
        "itens_por_pagina": itens_por_pagina,
        "vendedores": Vendedor.objects.all(),
        "locais": Local.objects.all(),
        "extra_query": extra_query,
    }
    return render(request, "contratos/contratos.html", context)

@login_required
def contrato_create(request):
    cliente_existente = None
    data_ultima_parcela = None

    if request.method == "POST":
        cliente_form = ClienteForm(request.POST)
        contrato_form = ContratoForm(request.POST)
        documento_form = DocumentoContratoForm(request.POST, request.FILES)
        video_formset = VideoFormSet(request.POST, prefix='video')

        if (
            cliente_form.is_valid()
            and contrato_form.is_valid()
            and documento_form.is_valid()
            and video_formset.is_valid()
        ):
            # 🔎 Verifica se já existe cliente com o mesmo CPF/CNPJ
            cpf_cnpj = cliente_form.cleaned_data.get("cpf_cnpj")
            cliente = Cliente.objects.filter(cpf_cnpj=cpf_cnpj).first()

            if cliente:
                cliente_existente = cliente
                messages.info(
                    request,
                    f"⚠ Cliente {cliente.razao_social} ({cliente.cpf_cnpj}) já existe e será reutilizado.",
                )
            else:
                cliente = cliente_form.save(commit=False)
                cliente.created_by = request.user
                cliente.updated_by = request.user
                cliente.save()

            # Criar contrato
            contrato = contrato_form.save(commit=False)
            contrato.cliente = cliente
            contrato.created_by = request.user
            contrato.updated_by = request.user


            if contrato.data_vencimento_primeira_parcela:
                contrato.data_ultima_parcela = (
                    contrato.data_vencimento_primeira_parcela
                    + relativedelta(months=contrato.vigencia_meses - 1)
                )

            status_ativo, _ = StatusContrato.objects.get_or_create(
                nome_status="Ativo",
                defaults={"created_by": request.user, "updated_by": request.user},
            )
            contrato.status = status_ativo
            contrato.save()

            # Salvar vídeos vinculados
            video_formset.instance = contrato
            videos = video_formset.save(commit=False)
            for video in videos:
                video.contrato = contrato
                video.created_by = request.user
                video.updated_by = request.user
                video.save()
            video_formset.save()  # processa deletes

            # Salvar documento
            if documento_form.cleaned_data.get("arquivo"):
                documento = documento_form.save(commit=False)
                documento.contrato = contrato
                documento.created_by = request.user
                documento.updated_by = request.user
                documento.save()

            messages.success(request, "✅ Contrato criado com sucesso!")
            return redirect("contrato_detail", pk=contrato.pk)

        else:
            # ⚡ Mantém os valores calculados mesmo em caso de erro
            try:
                vigencia = int(request.POST.get("vigencia_meses", 0))
                mensalidade = float(request.POST.get("valor_mensalidade", 0))     
            except (ValueError, TypeError):
                vigencia = 0
                

            try:
                data_inicial = request.POST.get("data_vencimento_primeira_parcela")
                if data_inicial and vigencia:
                    data_inicial = datetime.strptime(data_inicial, "%Y-%m-%d").date()
                    data_ultima_parcela = data_inicial + relativedelta(
                        months=vigencia - 1
                    )
            except Exception:
                data_ultima_parcela = None

            # Mensagens de erro detalhadas
            for form_name, form in [
                ("Cliente", cliente_form),
                ("Contrato", contrato_form),
                ("Documento", documento_form),
            ]:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{form_name} - {field}: {error}")

            for i, form in enumerate(video_formset.forms):
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(
                            request, f"Vídeo #{i+1} - {field}: {error}"
                        )

    else:
        cliente_form = ClienteForm()
        contrato_form = ContratoForm(
            initial={"data_assinatura": timezone.now().date()}
        )
        documento_form = DocumentoContratoForm()
        video_formset = VideoFormSet(prefix='video')

    return render(
        request,
        "contratos/contrato_form.html",
        {
            "cliente_form": cliente_form,
            "contrato_form": contrato_form,
            "documento_form": documento_form,
            "video_formset": video_formset,
            "cliente_existente": cliente_existente,
            "data_ultima_parcela": data_ultima_parcela,
        },
    )


@login_required
def contrato_detail(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk)
    documentos = contrato.documentos.all()
    videos = contrato.videos.all()
    locais = Local.objects.all()  # Para popular o select no modal
    now = timezone.now()

    # Preparar vídeos pendentes e ativos
    videos_pendentes = videos.filter(status=False)
    videos_ativos = videos.filter(status=True)

    # Flags para pendências
    tem_video_pendente = videos_pendentes.exists()
    tem_cobranca_pendente = not contrato.cobranca_gerada
    tem_pagamento_pendente = contrato.cobranca_gerada and (
        not contrato.primeiro_pagamento or not contrato.segundo_pagamento
    )

    if request.method == "POST":
        form = DocumentoContratoForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.contrato = contrato
            documento.created_by = request.user
            documento.updated_by = request.user
            documento.save()
            messages.success(request, "📂 Documento anexado com sucesso!")
            return redirect("contrato_detail", pk=contrato.pk)
    else:
        form = DocumentoContratoForm()

    return render(request, "contratos/contrato_detail.html", {
        "contrato": contrato,
        "documentos": documentos,
        "documento_form": form,
        "videos": videos,
        "videos_pendentes": videos_pendentes,
        "videos_ativos": videos_ativos,
        "tem_video_pendente": tem_video_pendente,
        "tem_cobranca_pendente": tem_cobranca_pendente,
        "tem_pagamento_pendente": tem_pagamento_pendente,
        "locais": locais,
        "now": now,
    })



@login_required
def pendencias_video(request):
    # Filtra contratos que têm pelo menos um vídeo OFF
    # e que já possuem primeiro_pagamento
    contratos = (
        Contrato.objects.annotate(
            videos_pendentes=Count("videos", filter=Q(videos__status=False))
        )
        .filter(videos_pendentes__gt=0, primeiro_pagamento__isnull=False)
        .select_related("cliente")
        .prefetch_related("videos")  # otimiza query dos vídeos
    )

    return render(request, "pendencias/pendencias_video.html", {"contratos": contratos})


# views.py
@login_required
def pendencias_pagamento(request):
    # pendências de cobrança (cobrança ainda não gerada)
    pendencias_cobranca = Contrato.objects.filter(
        cobranca_gerada=False
    ).select_related("cliente")

    # pendências de pagamento (cobrança gerada, mas falta algum pagamento)
    pendencias_pagamento = Contrato.objects.filter(
        cobranca_gerada=True
    ).filter(
        Q(primeiro_pagamento__isnull=True) | Q(segundo_pagamento__isnull=True)
    ).select_related("cliente")

    context = {
        "pendencias_cobranca": pendencias_cobranca,
        "pendencias_pagamento": pendencias_pagamento,
    }
    return render(request, "pendencias/pendencias_pagamento.html", context)



@login_required
def marcar_cobranca_gerada(request, contrato_id):
    contrato = get_object_or_404(Contrato, id_contrato=contrato_id)
    contrato.cobranca_gerada = True
    contrato.updated_by = request.user
    contrato.save()
    messages.success(request, f"Cobrança do contrato #{contrato.id_contrato} foi marcada como gerada.")
    return redirect("pendencias_pagamento")


@login_required
def marcar_pagamento(request, contrato_id, parcela):
    contrato = get_object_or_404(Contrato, pk=contrato_id)

    if request.method == "POST":
        data = request.POST.get("data_pagamento")
        if data:
            data_pagto = datetime.strptime(data, "%Y-%m-%d").date()
        else:
            data_pagto = timezone.now().date()

        if parcela == 1:
            contrato.primeiro_pagamento = data_pagto
        elif parcela == 2:
            contrato.segundo_pagamento = data_pagto
        contrato.updated_by = request.user
        contrato.save()
        messages.success(
            request,
            f"{'Primeiro' if parcela==1 else 'Segundo'} pagamento do contrato {contrato.id_contrato:05d} registrado em {data_pagto}."
        )

        # Redirecionamento inteligente
        next_page = request.POST.get("from_detail")
        if next_page:
            return redirect("contrato_detail", contrato.pk)
        return redirect("pendencias_pagamento")

    return redirect("pendencias_pagamento")



@login_required
def ativar_video(request, video_id):
    video = get_object_or_404(Video, pk=video_id)

    if request.method == "POST":
        data_subiu_str = request.POST.get("data_subiu")
        if data_subiu_str:
            try:
                video.data_subiu = datetime.strptime(data_subiu_str, "%Y-%m-%d").date()
            except ValueError:
                video.data_subiu = timezone.now().date()
        else:
            video.data_subiu = timezone.now().date()
        video.updated_by = request.user        
        video.status = True
        video.save()
        messages.success(request, f"🎬 Vídeo {video.id} ativado com sucesso!")

        # Redirecionamento inteligente
        from_detail = request.POST.get("from_detail")
        if from_detail:
            return redirect("contrato_detail", pk=video.contrato.pk)

    return redirect("pendencias_video")




@login_required
def documento_delete(request, pk):
    documento = get_object_or_404(DocumentoContrato, pk=pk)
    contrato_id = documento.contrato.id_contrato
    if request.method == "POST":
        documento.delete()
        messages.success(request, "Documento excluído com sucesso!")
    return redirect("contrato_detail", pk=contrato_id)


@login_required
def video_create_modal(request, contrato_id):
    contrato = get_object_or_404(Contrato, pk=contrato_id)

    if request.method == "POST":
        tempo_segundos = int(request.POST.get("tempo_video", 0))
        local_id = request.POST.get("local")

        if tempo_segundos > 0 and local_id:
            local = get_object_or_404(Local, pk=local_id)
            video = Video.objects.create(
                contrato=contrato,
                tempo_video=timedelta(seconds=tempo_segundos),
                local=local,
                created_by=request.user,
                updated_by=request.user
            )
            messages.success(request, "🎬 Vídeo adicionado com sucesso!")
        else:
            messages.error(request, "❌ Preencha todos os campos corretamente.")

    return redirect("contrato_detail", pk=contrato.pk)


@login_required
def contratos_vencendo(request):
    hoje = timezone.now().date()
    limite = hoje + relativedelta(months=2)

    contratos = (
        Contrato.objects.filter(
            data_vencimento_contrato__isnull=False,
            data_cancelamento_contrato__isnull=True,
            data_vencimento_contrato__lte=limite,
        )
        .select_related("cliente")
        .order_by("data_vencimento_contrato")
    )

    try:
        itens_por_pagina = int(request.GET.get("itens", 10))
        if itens_por_pagina <= 0:
            itens_por_pagina = 10
    except ValueError:
        itens_por_pagina = 10

    paginator = Paginator(contratos, itens_por_pagina)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    params = request.GET.copy()
    params.pop("page", None)
    extra_query = "&" + params.urlencode() if params else ""

    return render(request, "contratos/contratos_vencendo.html", {
        "page_obj": page_obj,
        "hoje": hoje,
        "itens_por_pagina": itens_por_pagina,
        "extra_query": extra_query,
    })


@login_required
def renovar_contrato(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk)

    if contrato.data_vencimento_contrato:
        contrato.data_vencimento_contrato += relativedelta(months=1)
        contrato.updated_by = request.user
        contrato.save()
        messages.success(
            request,
            f"📅 Contrato #{contrato.id_contrato} renovado por mais 30 dias (novo vencimento: {contrato.data_vencimento_contrato.strftime('%d/%m/%Y')}).",
        )
    else:
        messages.warning(request, f"⚠ O contrato #{contrato.id_contrato} não possui data de vencimento definida.")

    return redirect("contratos_vencendo")


@login_required
def dashboard_view(request):
    vendedor_id = request.GET.get("vendedor")  # filtro opcional por vendedor
    mes = request.GET.get("mes")  # filtro opcional por mês (formato YYYY-MM)
    
    if mes == None or mes == "":
        mes = datetime.now().strftime("%Y-%m")  # padrão para mês atual

    

    data = dashboard_service.get_dashboard_data(vendedor_id, mes)
    
    faturamento_mes = data["faturamento_por_mes"]

    labels_faturamento = [f"{item['mes']}/{item['ano']}" for item in faturamento_mes]
    data_faturamento = [float(item['faturamento_total']) for item in faturamento_mes]

    return render(request, "dashboard.html", {
        "data": data,
        "vendedores": data["vendedores"],  # lista de vendedores p/ select
        "selected_vendedor": vendedor_id,
        "selected_mes": mes,
        "labels_faturamento": labels_faturamento,
        "data_faturamento": data_faturamento,
    })


@login_required
def exportar_contratos_excel(request):
    qs = Contrato.objects.select_related(
        "cliente", "vendedor", "forma_pagamento", "status", "banco"
    ).prefetch_related("videos__local")

    # ----- FILTROS -----
    nome = request.GET.get("nome")
    if nome:
        qs = qs.filter(cliente__razao_social__icontains=nome)

    cnpj = request.GET.get("cnpj")
    if cnpj:
        qs = qs.filter(cliente__cpf_cnpj__icontains=cnpj)

    vendedor = request.GET.get("vendedor")
    if vendedor:
        qs = qs.filter(vendedor_id=vendedor)

    local = request.GET.get("local")
    if local:
        qs = qs.filter(videos__local_id=local)

    data_inicio = request.GET.get("data_inicio")
    data_fim = request.GET.get("data_fim")
    if data_inicio and data_fim:
        qs = qs.filter(data_assinatura__range=[data_inicio, data_fim])
    elif data_inicio:
        qs = qs.filter(data_assinatura__gte=data_inicio)
    elif data_fim:
        qs = qs.filter(data_assinatura__lte=data_fim)

    # ----- DADOS -----
    data = []
    for contrato in qs:
        locais = ", ".join([v.local.nome for v in contrato.videos.all() if v.local])
        status_videos = ", ".join(["ON" if v.status else "OFF" for v in contrato.videos.all()]) or "Sem vídeo"
        tempos_videos = ", ".join([str(v.tempo_video) for v in contrato.videos.all()])
        datas_subida = ", ".join([v.data_subiu.strftime("%d/%m/%Y") for v in contrato.videos.all() if v.data_subiu])

        data.append({
            "ID Contrato": contrato.id_contrato,
            "Cliente": contrato.cliente.razao_social,
            "CPF/CNPJ": contrato.cliente.cpf_cnpj,
            "Email Cliente": contrato.cliente.email,
            "Telefone Cliente": contrato.cliente.telefone,
            "Telefone Financeiro": contrato.cliente.telefone_financeiro,
            "Email Financeiro": contrato.cliente.email_financeiro,
            "Vendedor": contrato.vendedor.nome if contrato.vendedor else "",
            "Banco": contrato.banco.nome if contrato.banco else "",
            "Cobrança Gerada": "Sim" if contrato.cobranca_gerada else "Não",
            "Primeiro Pagamento": contrato.primeiro_pagamento.strftime("%d/%m/%Y") if contrato.primeiro_pagamento else "",
            "Segundo Pagamento": contrato.segundo_pagamento.strftime("%d/%m/%Y") if contrato.segundo_pagamento else "",
            "Data Assinatura": contrato.data_assinatura.strftime("%d/%m/%Y") if contrato.data_assinatura else "",
            "Data Vencimento Contrato": contrato.data_vencimento_contrato.strftime("%d/%m/%Y") if contrato.data_vencimento_contrato else "",
            "Data Cancelamento": contrato.data_cancelamento_contrato.strftime("%d/%m/%Y") if contrato.data_cancelamento_contrato else "",
            "Data Vencimento 1ª Parcela": contrato.data_vencimento_primeira_parcela.strftime("%d/%m/%Y") if contrato.data_vencimento_primeira_parcela else "",
            "Data Última Parcela": contrato.data_ultima_parcela.strftime("%d/%m/%Y") if contrato.data_ultima_parcela else "",
            "Valor Mensalidade": contrato.valor_mensalidade,
            "Vigência (meses)": contrato.vigencia_meses,
            "Valor Total": contrato.valor_total,
            "Forma de Pagamento": contrato.forma_pagamento.nome if contrato.forma_pagamento else "",
            "Status Contrato": contrato.status.nome_status if contrato.status else "",
            "Telões": locais or "Sem local",
            "Status Vídeos": status_videos,
            "Tempo Vídeos": tempos_videos,
            "Datas Subida Vídeos": datas_subida,
            "Observações": contrato.observacoes or "",
        })

    # Criar DataFrame
    df = pd.DataFrame(data)

    # Gerar Excel em memória
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="contratos.xlsx"'

    with pd.ExcelWriter(response, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Contratos")

    return response


@login_required
def criar_contrato_registro(request, contrato_id):
    contrato = get_object_or_404(Contrato, id_contrato=contrato_id)
    if request.method == "POST":
        form = ContratoRegistroForm(request.POST)
        if form.is_valid():
            registro = form.save(commit=False)
            registro.contrato = contrato
            registro.created_by = request.user
            registro.updated_by = request.user
            registro.save()
            return redirect('contrato_detail', pk=contrato.pk)
    else:
        form = ContratoRegistroForm()