import datetime
import os

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FacturaForm, TelevisorForm
from .models import Factura, PinCodeGenerado, RegistroSync, SyncJob, SyncJobItem, Televisor


def login_view(request):
    """Página de login. Inicia sesión usando correo y contraseña."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')

        messages.error(request, 'Correo o contraseña incorrectos.')

    return render(request, 'whaletv/login.html')


@login_required
def home_view(request):
    """Página de inicio, visible solo cuando el usuario ha iniciado sesión."""
    return render(request, 'whaletv/home.html')


def logout_view(request):
    """Cierra la sesión y vuelve al login."""
    logout(request)
    return redirect('login')


# ---------------------------------------------------------------------------
# CRUD de Televisores
# ---------------------------------------------------------------------------

@login_required
def televisor_list(request):
    """Lista todos los televisores, con búsqueda opcional."""
    # Recalcula los estados (vencida/bloqueado) según la fecha de hoy.
    Televisor.refrescar_todos()

    query = request.GET.get('q', '').strip()
    televisores = Televisor.objects.all()

    if query:
        televisores = televisores.filter(
            Q(mac_address__icontains=query)
            | Q(serial_number__icontains=query)
            | Q(nombre_persona__icontains=query)
            | Q(correo_persona__icontains=query)
        )

    return render(request, 'whaletv/televisor_list.html', {
        'televisores': televisores,
        'query': query,
    })


@login_required
def televisor_create(request):
    """Crea un televisor nuevo."""
    if request.method == 'POST':
        form = TelevisorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Televisor creado correctamente.')
            return redirect('televisor_list')
    else:
        form = TelevisorForm()

    return render(request, 'whaletv/televisor_form.html', {
        'form': form,
        'titulo': 'Nuevo televisor',
    })


@login_required
def televisor_update(request, pk):
    """Edita un televisor existente."""
    televisor = get_object_or_404(Televisor, pk=pk)

    if request.method == 'POST':
        form = TelevisorForm(request.POST, instance=televisor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Televisor actualizado correctamente.')
            return redirect('televisor_list')
    else:
        form = TelevisorForm(instance=televisor)

    return render(request, 'whaletv/televisor_form.html', {
        'form': form,
        'titulo': 'Editar televisor',
        'televisor': televisor,
    })


@login_required
def televisor_validar(request, pk):
    """Sincroniza (dry-run) el estado del televisor con el portal real de WhaleTV."""
    televisor = get_object_or_404(Televisor, pk=pk)

    if request.method != 'POST':
        return redirect('televisor_list')

    from .portal_sync import sincronizar_televisor

    resultado = sincronizar_televisor(televisor, dry_run=True)

    def estado(b):
        if b is None:
            return '¿?'
        return 'Bloqueado' if b else 'Desbloqueado'

    if resultado.ok:
        base = (
            f'[{televisor.mac_address}] DRY-RUN · '
            f'Portal: {estado(resultado.remoto_bloqueado)} | '
            f'App: {estado(resultado.local_bloqueado)}'
        )
        if resultado.cambiaria:
            messages.warning(request, f'{base} → DEBERÍA cambiarse en el portal.')
        else:
            messages.success(request, f'{base} → coinciden, nada que cambiar.')
    else:
        messages.error(
            request,
            f'[{televisor.mac_address}] Error validando: {resultado.error}',
        )

    return redirect('televisor_list')


@login_required
def televisor_sincronizar(request, pk):
    """MODO REAL: aplica el estado local (lock + fecha) en el portal de WhaleTV."""
    televisor = get_object_or_404(Televisor, pk=pk)

    if request.method != 'POST':
        return redirect('televisor_list')

    from .portal_sync import sincronizar_televisor

    resultado = sincronizar_televisor(televisor, dry_run=False)

    if resultado.ok:
        RegistroSync.registrar(
            request.user, televisor,
            aplicado=resultado.aplicado, tipo='individual',
        )

    def estado(b):
        if b is None:
            return '¿?'
        return 'Bloqueado' if b else 'Desbloqueado'

    if resultado.ok:
        if resultado.aplicado:
            fecha = televisor.fecha_sincronizar
            messages.success(
                request,
                f'[{televisor.mac_address}] SINCRONIZADO en el portal → '
                f'quedó {estado(resultado.remoto_bloqueado)}'
                + (f' · fecha {fecha:%d/%m/%Y}' if fecha else ''),
            )
        else:
            messages.success(
                request,
                f'[{televisor.mac_address}] Ya estaba igual en el portal '
                f'({estado(resultado.remoto_bloqueado)}), no se cambió nada.',
            )
    else:
        messages.error(
            request,
            f'[{televisor.mac_address}] Error sincronizando: {resultado.error}',
        )

    return redirect('televisor_list')


@login_required
def televisor_delete(request, pk):
    """Elimina un televisor (con confirmación)."""
    televisor = get_object_or_404(Televisor, pk=pk)

    if request.method == 'POST':
        televisor.delete()
        messages.success(request, 'Televisor eliminado correctamente.')
        return redirect('televisor_list')

    return render(request, 'whaletv/televisor_confirm_delete.html', {
        'televisor': televisor,
    })


# ---------------------------------------------------------------------------
# Histórico de facturas de un televisor
# ---------------------------------------------------------------------------

@login_required
def televisor_sincronizar_todos(request):
    """MODO REAL: aplica el estado local de TODOS los televisores en el portal."""
    if request.method != 'POST':
        return redirect('televisor_list')

    from .portal_sync import sincronizar_todos

    Televisor.refrescar_todos()
    televisores = list(Televisor.objects.all())

    if not televisores:
        messages.warning(request, 'No hay televisores para sincronizar.')
        return redirect('televisor_list')

    resultados = sincronizar_todos(televisores, dry_run=False)

    for tv, r in resultados:
        if r.ok:
            RegistroSync.registrar(
                request.user, tv, aplicado=r.aplicado, tipo='masivo',
            )

    aplicados = sum(1 for _, r in resultados if r.ok and r.aplicado)
    sin_cambios = sum(1 for _, r in resultados if r.ok and not r.aplicado)
    fallidos = [(tv, r) for tv, r in resultados if not r.ok]

    if not fallidos:
        messages.success(
            request,
            f'Sincronización masiva lista: {aplicados} aplicados, '
            f'{sin_cambios} sin cambios, {len(resultados)} en total.',
        )
    else:
        detalle = '; '.join(f'{tv.mac_address}: {r.error}' for tv, r in fallidos[:5])
        messages.warning(
            request,
            f'Sincronización masiva: {aplicados} aplicados, {sin_cambios} sin cambios, '
            f'{len(fallidos)} con error → {detalle}',
        )

    return redirect('televisor_list')


@login_required
def sync_iniciar(request):
    """Lanza una sincronización masiva en segundo plano (no bloquea la web)."""
    if request.method != 'POST':
        return redirect('televisor_list')

    import datetime
    import threading

    from django.utils import timezone

    from .portal_sync import ejecutar_job

    # Auto-recupera jobs "colgados": si quedó activo pero sin actividad por
    # varios minutos (server reiniciado / hilo muerto), lo damos por cancelado
    # para no bloquear nuevas sincronizaciones.
    limite = timezone.now() - datetime.timedelta(minutes=10)
    SyncJob.objects.filter(
        estado__in=SyncJob.ACTIVOS, actualizado__lt=limite
    ).update(
        estado='cancelado',
        terminado=timezone.now(),
        error='Cancelado automáticamente (sin actividad).',
    )

    # Si ya hay una realmente en curso, vamos a su progreso en vez de duplicar.
    activo = SyncJob.objects.filter(estado__in=SyncJob.ACTIVOS).first()
    if activo:
        messages.info(
            request,
            'Ya hay una sincronización en curso. Puedes cancelarla aquí si se quedó pegada.',
        )
        return redirect('sync_progreso', pk=activo.pk)

    Televisor.refrescar_todos()
    televisores = list(Televisor.objects.all())
    if not televisores:
        messages.warning(request, 'No hay televisores para sincronizar.')
        return redirect('televisor_list')

    # 1 TV → 1 navegador, 2 → 2, 3 → 3, 4 o más → siempre 4.
    workers = max(1, min(len(televisores), 4))

    job = SyncJob.objects.create(
        total=len(televisores),
        workers=workers,
        usuario=request.user,
        usuario_email=getattr(request.user, 'email', '') or '',
    )
    SyncJobItem.objects.bulk_create([
        SyncJobItem(job=job, televisor=tv, mac=tv.mac_address) for tv in televisores
    ])

    hilo = threading.Thread(
        target=ejecutar_job, args=(job.pk, workers), daemon=True,
    )
    hilo.start()

    return redirect('sync_progreso', pk=job.pk)


@login_required
def sync_cambios(request):
    """Sincroniza SOLO los televisores que cambiaron de estado tras una importación.

    Asigna 1 navegador por televisor, con un tope de 4 (1→1, 2→2, 3→3, 4+→4).
    """
    if request.method != 'POST':
        return redirect('televisor_list')

    import datetime
    import threading

    from django.utils import timezone

    from .portal_sync import ejecutar_job

    pks = request.session.get('sync_cambios_pks') or []
    televisores = list(Televisor.objects.filter(pk__in=pks))
    if not televisores:
        messages.info(request, 'No hay cambios pendientes por sincronizar.')
        return redirect('televisor_list')

    # Auto-recupera jobs "colgados" (igual que en sync_iniciar).
    limite = timezone.now() - datetime.timedelta(minutes=10)
    SyncJob.objects.filter(
        estado__in=SyncJob.ACTIVOS, actualizado__lt=limite
    ).update(
        estado='cancelado',
        terminado=timezone.now(),
        error='Cancelado automáticamente (sin actividad).',
    )

    activo = SyncJob.objects.filter(estado__in=SyncJob.ACTIVOS).first()
    if activo:
        messages.info(
            request,
            'Ya hay una sincronización en curso. Puedes cancelarla aquí si se quedó pegada.',
        )
        return redirect('sync_progreso', pk=activo.pk)

    # 1 TV → 1 navegador, 2 → 2, 3 → 3, 4 o más → siempre 4.
    workers = max(1, min(len(televisores), 4))

    job = SyncJob.objects.create(
        total=len(televisores),
        workers=workers,
        usuario=request.user,
        usuario_email=getattr(request.user, 'email', '') or '',
    )
    SyncJobItem.objects.bulk_create([
        SyncJobItem(job=job, televisor=tv, mac=tv.mac_address) for tv in televisores
    ])

    request.session.pop('sync_cambios_pks', None)

    hilo = threading.Thread(
        target=ejecutar_job, args=(job.pk, workers), daemon=True,
    )
    hilo.start()

    return redirect('sync_progreso', pk=job.pk)


@login_required
def sync_cancelar(request, pk=None):
    """Cancela una sincronización (o todas las que estén activas)."""
    if request.method != 'POST':
        return redirect('televisor_list')

    from django.utils import timezone

    activos = SyncJob.objects.filter(estado__in=SyncJob.ACTIVOS)
    if pk:
        activos = activos.filter(pk=pk)

    n = activos.update(
        estado='cancelado',
        terminado=timezone.now(),
        error='Cancelado por el usuario.',
    )

    if n:
        messages.success(
            request,
            'Sincronización cancelada. Ya puedes lanzar una nueva.'
            if n == 1 else
            f'{n} sincronizaciones canceladas. Ya puedes lanzar una nueva.',
        )
    else:
        messages.info(request, 'No había ninguna sincronización en curso.')

    return redirect('televisor_list')


@login_required
def sync_progreso(request, pk):
    """Página con la barra de progreso de la sincronización (hace polling)."""
    job = get_object_or_404(SyncJob, pk=pk)
    return render(request, 'whaletv/sync_progress.html', {'job': job})


@login_required
def sync_progreso_api(request, pk):
    """Devuelve el progreso del job en JSON (para el polling)."""
    job = get_object_or_404(SyncJob, pk=pk)
    items = job.items.all()

    ok = items.filter(estado='ok').count()
    error = items.filter(estado='error').count()
    aplicados = items.filter(estado='ok', aplicado=True).count()
    sin_cambios = items.filter(estado='ok', aplicado=False).count()
    procesados = ok + error
    total = job.total or items.count()
    pct = round(procesados * 100 / total) if total else 100

    errores = list(
        items.filter(estado='error').values('mac', 'mensaje')[:100]
    )

    return JsonResponse({
        'estado': job.estado,
        'total': total,
        'procesados': procesados,
        'ok': ok,
        'error': error,
        'aplicados': aplicados,
        'sin_cambios': sin_cambios,
        'porcentaje': pct,
        'terminado': job.estado in ('terminado', 'error', 'cancelado'),
        'errores': errores,
    })


@login_required
def registro_sync_list(request):
    """Bitácora: quién sincronizó cada televisor (nombre + MAC) y cuándo."""
    query = request.GET.get('q', '').strip()
    registros = RegistroSync.objects.select_related('usuario', 'televisor')

    if query:
        registros = registros.filter(
            Q(mac_address__icontains=query)
            | Q(nombre_persona__icontains=query)
            | Q(usuario_email__icontains=query)
        )

    return render(request, 'whaletv/registro_sync_list.html', {
        'registros': registros[:500],
        'query': query,
        'total': registros.count(),
    })


@login_required
def pincode_list(request):
    """Bitácora de Pin Codes generados (MAC + Passcode + Pin Code)."""
    query = request.GET.get('q', '').strip()
    registros = PinCodeGenerado.objects.select_related('usuario')

    if query:
        registros = registros.filter(
            Q(mac_address__icontains=query)
            | Q(pin_code__icontains=query)
            | Q(passcode__icontains=query)
            | Q(usuario_email__icontains=query)
        )

    return render(request, 'whaletv/pincode_list.html', {
        'registros': registros[:500],
        'query': query,
        'total': registros.count(),
    })


@login_required
def registro_sync_tv(request, mac):
    """Detalle de un televisor (tarjeta de info). Las sincronizaciones y los
    pin codes se ven en páginas aparte."""
    televisor = Televisor.objects.filter(mac_address=mac).first()
    return render(request, 'whaletv/registro_sync_tv.html', {
        'mac': mac,
        'televisor': televisor,
        'total': RegistroSync.objects.filter(mac_address=mac).count(),
        'total_pincodes': PinCodeGenerado.objects.filter(mac_address=mac).count(),
    })


@login_required
def registro_sync_tv_records(request, mac):
    """Página con la tabla de sincronizaciones de un televisor."""
    registros = RegistroSync.objects.filter(mac_address=mac).select_related('usuario')
    televisor = Televisor.objects.filter(mac_address=mac).first()
    return render(request, 'whaletv/registro_sync_tv_records.html', {
        'registros': registros,
        'mac': mac,
        'televisor': televisor,
        'total': registros.count(),
    })


@login_required
def registro_sync_tv_pincodes(request, mac):
    """Página con la tabla de Pin Codes generados de un televisor."""
    pincodes = PinCodeGenerado.objects.filter(mac_address=mac).select_related('usuario')
    televisor = Televisor.objects.filter(mac_address=mac).first()
    return render(request, 'whaletv/registro_sync_tv_pincodes.html', {
        'pincodes': pincodes,
        'mac': mac,
        'televisor': televisor,
        'total': pincodes.count(),
    })


@login_required
def desbloquear_manual(request, mac):
    """Genera un Pin Code en el portal de Locking System usando el Passcode dado.

    Responde JSON (lo consume el modal de la página vía fetch).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)

    passcode = (request.POST.get('passcode') or '').strip()
    if not passcode:
        return JsonResponse({'ok': False, 'error': 'Debes ingresar el Passcode.'}, status=400)

    from .portal_sync import generar_pin_code

    res, pin = generar_pin_code(mac, passcode)

    if res.ok and pin:
        PinCodeGenerado.objects.create(
            usuario=request.user if getattr(request.user, 'pk', None) else None,
            usuario_email=getattr(request.user, 'email', '') or '',
            mac_address=mac,
            passcode=passcode,
            pin_code=pin,
        )
        return JsonResponse({'ok': True, 'pin': pin, 'mac': mac})

    return JsonResponse({
        'ok': False,
        'error': res.error or 'No se pudo generar el Pin Code.',
        'log': res.log[-6:],
    })


@login_required
def desbloquear_sincronizar(request, mac):
    """Sincroniza (modo real) el estado + fecha de la factura del TV con el portal.

    Es lo mismo que el botón 'Sincronizar', pero invocado por AJAX desde el modal
    de Desbloquear Manual al pulsar 'Listo'. Responde JSON.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)

    televisor = Televisor.objects.filter(mac_address=mac).first()
    if not televisor:
        return JsonResponse({'ok': False, 'error': 'No existe un televisor con esa MAC.'}, status=404)

    from django.urls import reverse

    from .portal_sync import sincronizar_televisor

    resultado = sincronizar_televisor(televisor, dry_run=False)

    def estado(b):
        if b is None:
            return '¿?'
        return 'Bloqueado' if b else 'Desbloqueado'

    if resultado.ok:
        RegistroSync.registrar(
            request.user, televisor, aplicado=resultado.aplicado, tipo='individual',
        )
        if resultado.aplicado:
            fecha = televisor.fecha_sincronizar
            messages.success(
                request,
                f'[{televisor.mac_address}] SINCRONIZADO en el portal → '
                f'quedó {estado(resultado.remoto_bloqueado)}'
                + (f' · fecha {fecha:%d/%m/%Y}' if fecha else ''),
            )
        else:
            messages.success(
                request,
                f'[{televisor.mac_address}] Ya estaba igual en el portal '
                f'({estado(resultado.remoto_bloqueado)}), no se cambió nada.',
            )
        return JsonResponse({'ok': True, 'redirect': reverse('televisor_list')})

    messages.error(
        request,
        f'[{televisor.mac_address}] Error sincronizando: {resultado.error}',
    )
    return JsonResponse({'ok': False, 'error': resultado.error or 'No se pudo sincronizar.'})


@login_required
def registro_sync_tv_export(request, mac):
    """Exporta a Excel las sincronizaciones de un televisor (por MAC)."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    registros = RegistroSync.objects.filter(mac_address=mac).select_related('usuario')
    televisor = Televisor.objects.filter(mac_address=mac).first()

    wb = Workbook()
    ws = wb.active
    ws.title = 'Sincronizaciones'

    headers = ['Fecha', 'Quién sincronizó', 'Persona', 'Mac Address', 'Estado', 'Resultado', 'Tipo']
    ws.append(headers)
    header_fill = PatternFill('solid', fgColor='F6186A')
    header_font = Font(bold=True, color='FFFFFF')
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    for r in registros:
        ws.append([
            r.creado.strftime('%d/%m/%Y %H:%M'),
            r.usuario_email or '—',
            r.nombre_persona or (televisor.nombre_persona if televisor else '—'),
            r.mac_address,
            'Bloqueado' if r.lock_status else 'Desbloqueado',
            'Aplicado' if r.aplicado else 'Sin cambios',
            r.get_tipo_display(),
        ])

    for col, ancho in zip('ABCDEFG', (18, 26, 22, 20, 14, 14, 12)):
        ws.column_dimensions[col].width = ancho

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    nombre_archivo = f"sync_{mac.replace(':', '-')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


@login_required
def registro_sync_tv_pincodes_export(request, mac):
    """Exporta a Excel los Pin Codes generados de un televisor (por MAC)."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    pincodes = PinCodeGenerado.objects.filter(mac_address=mac).select_related('usuario')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Pin Codes'

    headers = ['Fecha', 'Mac Address', 'Passcode', 'Pin Code', 'Quién lo generó']
    ws.append(headers)
    header_fill = PatternFill('solid', fgColor='F6186A')
    header_font = Font(bold=True, color='FFFFFF')
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    for p in pincodes:
        ws.append([
            p.creado.strftime('%d/%m/%Y %H:%M'),
            p.mac_address,
            p.passcode,
            p.pin_code,
            p.usuario_email or '—',
        ])

    for col, ancho in zip('ABCDE', (18, 20, 16, 16, 26)):
        ws.column_dimensions[col].width = ancho

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    nombre_archivo = f"pincodes_{mac.replace(':', '-')}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


@login_required
def televisor_historico(request, pk):
    """Lista las facturas (cuotas) del televisor y permite agregar una nueva."""
    televisor = get_object_or_404(Televisor, pk=pk)

    if request.method == 'POST':
        form = FacturaForm(request.POST)
        if form.is_valid():
            factura = form.save(commit=False)
            factura.televisor = televisor
            factura.save()
            messages.success(request, 'Factura agregada correctamente.')
            return redirect('televisor_historico', pk=televisor.pk)
    else:
        form = FacturaForm()

    facturas = televisor.facturas.all()
    return render(request, 'whaletv/televisor_historico.html', {
        'televisor': televisor,
        'facturas': facturas,
        'form': form,
    })


@login_required
def factura_toggle(request, pk):
    """Marca/desmarca una factura como pagada (recalcula el bloqueo del TV)."""
    factura = get_object_or_404(Factura, pk=pk)
    if request.method == 'POST':
        factura.pagada = not factura.pagada
        factura.save()
        estado = 'pagada' if factura.pagada else 'pendiente'
        messages.success(request, f'Factura {factura.numero_factura} marcada como {estado}.')
    return redirect('televisor_historico', pk=factura.televisor_id)


@login_required
def factura_update(request, pk):
    """Edita una factura (solo los campos no calculados)."""
    factura = get_object_or_404(Factura, pk=pk)

    if request.method == 'POST':
        form = FacturaForm(request.POST, instance=factura)
        if form.is_valid():
            form.save()
            messages.success(request, 'Factura actualizada correctamente.')
            return redirect('televisor_historico', pk=factura.televisor_id)
    else:
        form = FacturaForm(instance=factura)

    return render(request, 'whaletv/factura_form.html', {
        'form': form,
        'factura': factura,
        'televisor': factura.televisor,
    })


@login_required
def factura_delete(request, pk):
    """Elimina una factura."""
    factura = get_object_or_404(Factura, pk=pk)
    tv_id = factura.televisor_id
    if request.method == 'POST':
        factura.delete()
        messages.success(request, 'Factura eliminada.')
    return redirect('televisor_historico', pk=tv_id)


# ---------------------------------------------------------------------------
# Importación masiva de facturas (CSV / Excel)
# ---------------------------------------------------------------------------

# Sinónimos aceptados para cada columna (encabezados flexibles).
_COLUMNAS_FACTURA = {
    'mac_address': {'mac_address', 'mac', 'mac address'},
    'numero_factura': {'numero_factura', 'numero factura', 'n_factura', 'factura', 'num_factura'},
    'numero_cuota': {'numero_cuota', 'numero cuota', 'cuota', 'num_cuota', 'n_cuota'},
    'fecha_vencimiento': {'fecha_vencimiento', 'fecha vencimiento', 'fecha', 'vencimiento'},
    'pagada': {'pagada', 'pago', 'pagado'},
}

_COLUMNAS_TV = {
    'mac_address': {'mac_address', 'mac', 'mac address'},
    'serial_number': {'serial_number', 'serial', 'serial number', 'sn'},
    'nombre_persona': {'nombre_persona', 'nombre', 'persona', 'cliente', 'nombre persona'},
    'correo_persona': {'correo_persona', 'correo', 'email', 'e-mail', 'correo persona'},
    'numero_cuotas': {'numero_cuotas', 'cuotas', 'numero cuotas', 'n_cuotas', 'num_cuotas'},
}

_VERDADERO = {'si', 'sí', 'true', '1', 'x', 'pagada', 'pagado', 'yes', 'y', 'paid', 'verdadero'}


def _mapear_columnas(headers, columnas):
    """Devuelve {nombre_interno: nombre_real_en_archivo}."""
    mapa = {}
    for real in headers:
        clave = str(real).strip().lower()
        for interno, sinonimos in columnas.items():
            if clave in sinonimos:
                mapa[interno] = real
    return mapa


def _leer_dataframe(archivo):
    """Lee un CSV/Excel subido y devuelve un DataFrame (strings)."""
    import pandas as pd

    nombre = archivo.name.lower()
    if nombre.endswith(('.xlsx', '.xls')):
        return pd.read_excel(archivo, dtype=str)
    return pd.read_csv(archivo, dtype=str, sep=None, engine='python')


def _texto(valor):
    """Convierte un valor de celda a texto limpio ('' si vacío/NaN)."""
    if valor is None:
        return ''
    texto = str(valor).strip()
    return '' if texto.lower() in ('nan', 'nat', 'none') else texto


def _parse_fecha(valor):
    if valor is None:
        return None
    if isinstance(valor, (datetime.datetime, datetime.date)):
        return valor.date() if isinstance(valor, datetime.datetime) else valor
    texto = str(valor).strip()
    if not texto or texto.lower() in ('nan', 'nat'):
        return None
    texto = texto.split(' ')[0]  # por si viene con hora
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%m-%Y'):
        try:
            return datetime.datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _parse_bool(valor):
    if valor is None:
        return False
    return str(valor).strip().lower() in _VERDADERO


def _parse_entero(valor):
    try:
        return int(float(str(valor).strip()))
    except (ValueError, TypeError):
        return None


@login_required
def televisor_import(request):
    """Importa televisores/compras masivamente desde Excel/CSV (crea o actualiza)."""
    resultado = None

    if request.method == 'POST' and request.FILES.get('archivo'):
        try:
            df = _leer_dataframe(request.FILES['archivo'])
        except Exception as e:  # noqa: BLE001
            messages.error(request, f'No pude leer el archivo: {e}')
            return redirect('televisor_import')

        mapa = _mapear_columnas(df.columns, _COLUMNAS_TV)
        if 'mac_address' not in mapa:
            messages.error(
                request,
                'Falta la columna mac_address. Encabezados encontrados: '
                + ', '.join(str(c) for c in df.columns),
            )
            return redirect('televisor_import')

        creados, actualizados, errores = 0, 0, []

        for i, fila in df.iterrows():
            n = i + 2
            mac = _texto(fila[mapa['mac_address']])
            if not mac:
                errores.append(f'Fila {n}: falta MAC.')
                continue

            datos = {}
            if 'serial_number' in mapa:
                datos['serial_number'] = _texto(fila[mapa['serial_number']])
            if 'nombre_persona' in mapa:
                datos['nombre_persona'] = _texto(fila[mapa['nombre_persona']])
            if 'correo_persona' in mapa:
                datos['correo_persona'] = _texto(fila[mapa['correo_persona']])
            if 'numero_cuotas' in mapa:
                cuotas = _parse_entero(fila[mapa['numero_cuotas']])
                datos['numero_cuotas'] = cuotas if cuotas is not None else 0

            tv = Televisor.objects.filter(mac_address__iexact=mac).first()
            if tv is None:
                Televisor.objects.create(
                    mac_address=mac,
                    serial_number=datos.get('serial_number', ''),
                    nombre_persona=datos.get('nombre_persona', ''),
                    correo_persona=datos.get('correo_persona', ''),
                    numero_cuotas=datos.get('numero_cuotas', 0),
                )
                creados += 1
            else:
                for campo, valor in datos.items():
                    setattr(tv, campo, valor)
                tv.save()
                actualizados += 1

        resultado = {
            'creados': creados,
            'actualizados': actualizados,
            'errores': errores,
            'total': creados + actualizados,
        }
        if not errores:
            messages.success(
                request,
                f'Importación lista: {creados} creados, {actualizados} actualizados.',
            )
        else:
            messages.warning(
                request,
                f'Importación con avisos: {creados} creados, {actualizados} actualizados, '
                f'{len(errores)} con error.',
            )

    return render(request, 'whaletv/televisor_import.html', {'resultado': resultado})


@login_required
def televisor_plantilla(request):
    """Descarga una plantilla Excel (.xlsx) para importar televisores/compras."""
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = 'Televisores'
    ws.append(['mac_address', 'serial_number', 'nombre_persona', 'correo_persona', 'numero_cuotas'])
    ws.append(['B4:04:29:7E:3A:AA', 'B4:04:29:7E:3A:AA', 'Juan Pérez', 'juan@correo.com', 10])
    ws.append(['B4:04:29:7E:3A:BB', 'B4:04:29:7E:3A:BB', 'Ana Gómez', 'ana@correo.com', 12])
    for col, ancho in zip('ABCDE', (22, 22, 18, 22, 14)):
        ws.column_dimensions[col].width = ancho

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="plantilla_televisores.xlsx"'
    return response


@login_required
def factura_import(request):
    """Importa facturas masivamente desde CSV/Excel (crea o actualiza)."""
    resultado = None
    cambios = []

    if request.method == 'POST' and request.FILES.get('archivo'):
        try:
            df = _leer_dataframe(request.FILES['archivo'])
        except Exception as e:  # noqa: BLE001
            messages.error(request, f'No pude leer el archivo: {e}')
            return redirect('factura_import')

        mapa = _mapear_columnas(df.columns, _COLUMNAS_FACTURA)
        faltan = [c for c in ('mac_address', 'numero_factura', 'numero_cuota', 'fecha_vencimiento')
                  if c not in mapa]
        if faltan:
            messages.error(
                request,
                'Faltan columnas en el archivo: ' + ', '.join(faltan)
                + '. Encabezados encontrados: ' + ', '.join(str(c) for c in df.columns),
            )
            return redirect('factura_import')

        creadas, actualizadas, errores = 0, 0, []
        estado_antes = {}  # tv.pk -> lock_status antes de importar (para detectar cambios)

        for i, fila in df.iterrows():
            n = i + 2  # +2: fila 1 es encabezado, índice base 0
            mac = str(fila[mapa['mac_address']]).strip()
            num_factura = str(fila[mapa['numero_factura']]).strip()
            cuota = _parse_entero(fila[mapa['numero_cuota']])
            fecha = _parse_fecha(fila[mapa['fecha_vencimiento']])
            pagada = _parse_bool(fila[mapa['pagada']]) if 'pagada' in mapa else False

            if not mac or mac.lower() == 'nan':
                errores.append(f'Fila {n}: falta MAC.')
                continue
            if not num_factura or num_factura.lower() == 'nan':
                errores.append(f'Fila {n}: falta número de factura.')
                continue
            if cuota is None:
                errores.append(f'Fila {n}: número de cuota inválido.')
                continue
            if fecha is None:
                errores.append(f'Fila {n}: fecha de vencimiento inválida.')
                continue

            tv = Televisor.objects.filter(mac_address__iexact=mac).first()
            if tv is None:
                errores.append(f'Fila {n}: no existe un televisor con MAC {mac}.')
                continue

            # Guardamos el estado de bloqueo ANTES de tocar sus facturas.
            if tv.pk not in estado_antes:
                estado_antes[tv.pk] = tv.lock_status

            _, creada = Factura.objects.update_or_create(
                televisor=tv,
                numero_factura=num_factura,
                defaults={
                    'numero_cuota': cuota,
                    'fecha_vencimiento': fecha,
                    'pagada': pagada,
                },
            )
            if creada:
                creadas += 1
            else:
                actualizadas += 1

        resultado = {
            'creadas': creadas,
            'actualizadas': actualizadas,
            'errores': errores,
            'total': creadas + actualizadas,
        }
        if not errores:
            messages.success(
                request,
                f'Importación lista: {creadas} creadas, {actualizadas} actualizadas.',
            )
        else:
            messages.warning(
                request,
                f'Importación con avisos: {creadas} creadas, {actualizadas} actualizadas, '
                f'{len(errores)} con error.',
            )

        # Detecta televisores cuyo estado bloqueado/desbloqueado cambió tras la importación.
        cambiados = []
        for pk, antes in estado_antes.items():
            tv = Televisor.objects.get(pk=pk)
            if tv.lock_status != antes:
                cambiados.append(tv)

        # Guardamos los IDs en sesión para poder sincronizar solo esos televisores.
        request.session['sync_cambios_pks'] = [tv.pk for tv in cambiados]

        cambios = [{
            'mac': tv.mac_address,
            'serial': tv.serial_number,
            'fecha': tv.fecha_sincronizar,
            'lock': tv.lock_status,
            'cuotas_pagadas': tv.cuotas_pagadas,
            'numero_cuotas': tv.numero_cuotas,
        } for tv in cambiados]

    return render(request, 'whaletv/factura_import.html', {
        'resultado': resultado,
        'cambios': cambios,
        'n_cambios': len(cambios),
    })


@login_required
def factura_plantilla(request):
    """Descarga una plantilla Excel (.xlsx) de ejemplo para importar facturas."""
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = 'Facturas'
    ws.append(['mac_address', 'numero_factura', 'numero_cuota', 'fecha_vencimiento', 'pagada'])
    ws.append(['B4:04:29:7E:3A:EE', 'F-2026-007', 7, '2026-07-05', 'no'])
    ws.append(['B4:04:29:7E:3A:EE', 'F-2026-006', 6, '2026-06-05', 'si'])
    # Anchos cómodos para leer.
    for col, ancho in zip('ABCDE', (20, 16, 14, 18, 10)):
        ws.column_dimensions[col].width = ancho

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="plantilla_facturas.xlsx"'
    return response
