from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q, Count
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta, date

from .models import DocumentoVenta, DetalleDocumento, NotaCredito, DetalleNotaCredito, Pago
from .forms import DocumentoVentaForm, DetalleDocumentoForm, PagoForm, NotaCreditoForm, DetalleNotaFormSet

from apps.ventas.models import Pedido
from apps.productos.models import Producto
from apps.clientes.models import Cliente


@login_required
def listar_documentos(request):
    consulta_base = DocumentoVenta.objects.filter(tipo_documento='Factura')

    if request.user.rol == 'Cliente':
        try:
            perfil_cliente = request.user.perfil_cliente
            consulta_base = consulta_base.filter(cliente=perfil_cliente)
        except Cliente.DoesNotExist:
            consulta_base = consulta_base.none()
            messages.warning(request, "⚠️ Debes completar tu perfil para ver tus documentos.")

    facturas = (
        consulta_base
        .select_related('cliente', 'vendedor')
        .annotate(nc_count=Count('notas_credito'))
        .order_by('-fecha_emision')
    )

    hoy = timezone.localdate()
    for f in facturas:
        f.puede_crear_nota = False
        if f.fecha_emision:
            fecha_emision_date = f.fecha_emision.date() if hasattr(f.fecha_emision, 'date') else f.fecha_emision
            limite = fecha_emision_date + timedelta(days=30)
            f.puede_crear_nota = (hoy <= limite) and (f.estado != 'Anulada')

    return render(request, 'documentos/listar_documentos.html', {'facturas': facturas})


@login_required
def crear_documento_desde_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if hasattr(pedido, 'documento'):
        messages.warning(request, 'Este pedido ya tiene un documento asociado.')
        return redirect('documentos:detalle_documento', documento_id=pedido.documento.id)

    if request.method == 'POST':
        form = DocumentoVentaForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                documento = form.save(commit=False)
                documento.vendedor = request.user
                documento.pedido = pedido
                documento.cliente = pedido.cliente

                ultimo_folio = DocumentoVenta.objects.filter(
                    tipo_documento=documento.tipo_documento
                ).order_by('-folio').first()

                documento.folio = (ultimo_folio.folio + 1) if ultimo_folio else 1

                neto = Decimal('0')
                for detalle in pedido.detalles.all():
                    neto += detalle.subtotal

                documento.neto = neto
                documento.iva = neto * Decimal('0.19')
                documento.total = neto + documento.iva
                documento.save()

                for detalle_pedido in pedido.detalles.all():
                    DetalleDocumento.objects.create(
                        documento=documento,
                        producto=detalle_pedido.producto,
                        cantidad=detalle_pedido.cantidad,
                        precio_unitario_venta=detalle_pedido.precio_unitario,
                        costo_unitario_venta=detalle_pedido.producto.costo_unitario
                    )

                messages.success(request, f'{documento.tipo_documento} #{documento.folio} creada exitosamente.')
                return redirect('documentos:detalle_documento', documento_id=documento.id)

    else:
        form = DocumentoVentaForm(initial={'cliente': pedido.cliente})

    return render(request, 'documentos/crear_documento.html', {'form': form, 'pedido': pedido})


@login_required
def detalle_documento(request, documento_id):
    doc = get_object_or_404(DocumentoVenta.objects.select_related('cliente','vendedor'), id=documento_id)
    items = DetalleDocumento.objects.filter(documento=doc).select_related('producto')

    empresa = {
        'nombre': 'TICASHOP SPA',
        'rut': '99.999.999-9',
        'giro': 'Venta de productos tecnológicos',
        'direccion': 'Av. Ejemplo 1234',
        'ciudad': 'Santiago',
        'telefono': '+56 9 1234 5678',
        'email': 'contacto@ticashop.cl',
        'sucursal': 'SANTIAGO',
    }

    neto = doc.neto or Decimal('0')
    iva = doc.iva or Decimal('0')
    total = doc.total or (neto + iva)

    is_factura = (doc.tipo_documento == 'Factura')

    show_nc_button = False
    if is_factura and doc.fecha_emision:
        fecha_emision_date = doc.fecha_emision.date() if hasattr(doc.fecha_emision, 'date') else doc.fecha_emision
        limite = fecha_emision_date + timedelta(days=30)
        show_nc_button = (timezone.localdate() <= limite) and (doc.estado not in ['Anulada', 'Devuelta', 'Devuelta Parcial'])

    if request.user.rol == 'Cliente':
        show_nc_button = False

    context = {
        'doc': doc,
        'items': items,
        'empresa': empresa,
        'neto': neto,
        'iva': iva,
        'total': total,
        'is_factura': is_factura,
        'show_nc_button': show_nc_button,
    }
    return render(request, 'documentos/detalle_documento.html', context)


@login_required
def registrar_pago(request, documento_id):
    documento = get_object_or_404(DocumentoVenta, id=documento_id)

    if request.method == 'POST':
        form = PagoForm(request.POST, documento=documento)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.documento = documento

            if pago.monto_pagado > documento.saldo_pendiente:
                messages.error(request, f'El monto excede el saldo pendiente (${documento.saldo_pendiente})')
                return redirect('documentos:registrar_pago', documento_id=documento.id)

            pago.save()
            messages.success(request, 'Pago registrado exitosamente.')
            return redirect('documentos:detalle_documento', documento_id=documento.id)
    else:
        form = PagoForm(documento=documento, initial={'monto_pagado': documento.saldo_pendiente})

    return render(request, 'documentos/registrar_pago.html', {'form': form, 'documento': documento})


@login_required
def anular_documento(request, documento_id):
    documento = get_object_or_404(DocumentoVenta, id=documento_id)

    if request.method == 'POST':
        if documento.estado == 'Pagada':
            messages.error(request, 'No se puede anular un documento que ya está pagado.')
        else:
            documento.estado = 'Anulada'
            documento.save()
            messages.success(request, f'{documento.tipo_documento} #{documento.folio} anulada.')
        return redirect('documentos:listar_documentos')

    return render(request, 'documentos/confirmar_anular.html', {'documento': documento})


@login_required
def crear_nota_credito(request, factura_id):
    factura = get_object_or_404(DocumentoVenta, id=factura_id)

    if factura.fecha_emision:
        fecha_emision_date = factura.fecha_emision.date() if hasattr(factura.fecha_emision, 'date') else factura.fecha_emision
        limite = fecha_emision_date + timedelta(days=30)
        if timezone.localdate() > limite:
            messages.error(request, 'No se puede emitir una nota de crédito: la factura supera el plazo de 30 días.')
            return redirect('documentos:detalle_documento', documento_id=factura.id)

    items_factura = DetalleDocumento.objects.filter(documento=factura).select_related('producto')

    if request.method == 'POST':
        nota_form = NotaCreditoForm(request.POST)
        detalles_formset = DetalleNotaFormSet(request.POST)

        if nota_form.is_valid() and detalles_formset.is_valid():
            monto_total = Decimal('0')
            items_para_guardar = []

            for form in detalles_formset:
                prod_id = form.cleaned_data.get('producto_id')
                cantidad_dev = int(form.cleaned_data.get('cantidad') or 0)
                precio = form.cleaned_data.get('precio_unitario') or Decimal('0')

                original = next((it for it in items_factura if (it.producto and it.producto.id) == prod_id), None)
                cantidad_orig = original.cantidad if original else 0

                if cantidad_dev < 0 or cantidad_dev > cantidad_orig:
                    messages.error(request, f'Cantidad inválida para producto {original.producto.nombre if original else prod_id}. Máximo permitido: {cantidad_orig}')
                    return render(request, 'documentos/crear_nota_credito.html', {
                        'factura': factura,
                        'nota_form': nota_form,
                        'detalles_formset': detalles_formset,
                        'items': items_factura
                    })

                if cantidad_dev > 0:
                    subtotal = (Decimal(precio) or Decimal('0')) * cantidad_dev
                    monto_total += subtotal
                    items_para_guardar.append({
                        'producto': original.producto if original else None,
                        'descripcion': original.producto.nombre if original else '',
                        'cantidad': cantidad_dev,
                        'precio_unitario': Decimal(precio),
                        'subtotal': subtotal
                    })

            if monto_total <= 0:
                messages.error(request, 'Debes indicar al menos un producto con cantidad mayor a 0 para generar la nota.')
                return render(request, 'documentos/crear_nota_credito.html', {
                    'factura': factura,
                    'nota_form': nota_form,
                    'detalles_formset': detalles_formset,
                    'items': items_factura
                })

            try:
                with transaction.atomic():
                    nota = nota_form.save(commit=False)
                    nota.factura = factura
                    nota.usuario = request.user
                    nota.monto = monto_total
                    nota.save()

                    for it in items_para_guardar:
                        DetalleNotaCredito.objects.create(
                            nota=nota,
                            producto=it['producto'],
                            descripcion=it['descripcion'],
                            cantidad=it['cantidad'],
                            precio_unitario=it['precio_unitario'],
                            subtotal=it['subtotal']
                        )

                        prod = it['producto']
                        if prod:
                            try:
                                prod.stock = (prod.stock or 0) + int(it['cantidad'])
                                prod.save()
                            except:
                                pass

                    if monto_total >= (factura.total or Decimal('0')):
                        factura.estado = 'Devuelta'
                    else:
                        factura.estado = 'Devuelta Parcial'
                    factura.save()

            except Exception as e:
                messages.error(request, f'Error al crear la nota de crédito: {e}')
                return render(request, 'documentos/crear_nota_credito.html', {
                    'factura': factura,
                    'nota_form': nota_form,
                    'detalles_formset': detalles_formset,
                    'items': items_factura
                })

            messages.success(request, f'Nota de crédito creada correctamente (Monto: ${monto_total:,}).')
            return redirect('documentos:detalle_nota_credito', nota_id=nota.id)

    else:
        nota_form = NotaCreditoForm(initial={'fecha_emision': timezone.localdate()})
        initial_items = [{
            'producto_id': it.producto.id if it.producto else None,
            'producto_nombre': it.producto.nombre if it.producto else 'Sin nombre',
            'cantidad_original': it.cantidad,
            'cantidad': 0,
            'precio_unitario': it.precio_unitario_venta,
        } for it in items_factura]
        detalles_formset = DetalleNotaFormSet(initial=initial_items)

    return render(request, 'documentos/crear_nota_credito.html', {
        'factura': factura,
        'nota_form': nota_form,
        'detalles_formset': detalles_formset,
        'items': items_factura,
    })


@login_required
def detalle_nota_credito(request, nota_id):
    nota = get_object_or_404(NotaCredito.objects.select_related('factura', 'usuario'), id=nota_id)
    detalles = nota.detalles.select_related('producto').all()

    empresa = {
        'nombre': 'TICASHOP SPA',
        'rut': '99.999.999-9',
        'giro': 'Venta de productos tecnológicos',
        'direccion': 'Av. Ejemplo 1234',
        'ciudad': 'Santiago',
        'telefono': '+56 9 1234 5678',
        'email': 'contacto@ticashop.cl',
        'sucursal': 'SANTIAGO',
    }

    return render(request, 'documentos/detalle_nota_credito.html', {
        'nota': nota,
        'detalles': detalles,
        'empresa': empresa,
    })
