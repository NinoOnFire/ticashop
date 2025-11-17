from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Producto
from .forms import ProductoForm
import openpyxl
from .forms import ProductoForm, ImportCostoForm


def es_administrador(usuario):
    return usuario.is_authenticated and usuario.rol == 'Administrador'

def puede_ver_productos(usuario):
    return usuario.is_authenticated and usuario.rol in ['Administrador', 'Vendedor']

@login_required
@user_passes_test(puede_ver_productos)
def listar_productos(request):
    productos = Producto.objects.select_related('categoria', 'proveedor').all()

    # Filtro de búsqueda
    buscar = request.GET.get('buscar')
    if buscar:
        productos = productos.filter(nombre__icontains=buscar)

    return render(request, 'productos/listar_productos.html', {'productos': productos})


@login_required
@user_passes_test(es_administrador)
def crear_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto creado exitosamente.')
            return redirect('productos:listar_productos')
    else:
        form = ProductoForm()
    return render(request, 'productos/crear_producto.html', {'form': form})


@login_required
@user_passes_test(es_administrador)
def editar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto actualizado exitosamente.')
            return redirect('productos:listar_productos')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'productos/editar_producto.html', {'form': form, 'producto': producto})


@login_required
@user_passes_test(es_administrador)
def eliminar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    producto.delete()
    messages.success(request, 'Producto eliminado exitosamente.')
    return redirect('productos:listar_productos')

@login_required
@user_passes_test(es_administrador)
def importar_costos_excel(request):
    """
    Vista para subir el Excel de costos y actualizar masivamente los productos.
    """
    if request.method == 'POST':
        form = ImportCostoForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo_excel']
            
            # Cargar el libro de Excel
            try:
                wb = openpyxl.load_workbook(archivo)
                sheet = wb.active
            except Exception as e:
                messages.error(request, f"Error al leer el archivo Excel: {e}")
                return redirect('productos:importar_costos')

            productos_actualizados = 0
            productos_no_encontrados = []
            
            # Iterar sobre las filas (empezando desde la 2 para saltar el encabezado)
            for row in sheet.iter_rows(min_row=2, values_only=True):
                codigo_producto = row[0] # Columna A (CODIGO)
                costo_neto = row[1]      # Columna B (COSTO_NETO)

                if not codigo_producto or costo_neto is None:
                    continue # Ignorar filas vacías

                try:
                    # Buscar el producto por su código
                    producto = Producto.objects.get(codigo=str(codigo_producto).strip())
                    
                    # Actualizar el costo
                    producto.costo_unitario = Decimal(costo_neto)
                    producto.save()
                    productos_actualizados += 1
                    
                except Producto.DoesNotExist:
                    productos_no_encontrados.append(codigo_producto)
                except Exception as e:
                    messages.error(request, f"Error procesando la fila de {codigo_producto}: {e}")

            # Informar el resultado
            messages.success(request, f"✅ ¡Importación completada! {productos_actualizados} productos fueron actualizados.")
            if productos_no_encontrados:
                messages.warning(request, f"⚠️ Productos no encontrados (SKU no existe): {', '.join(map(str, productos_no_encontrados))}")
            
            return redirect('productos:listar_productos')

    else:
        form = ImportCostoForm()

    return render(request, 'productos/importar_costos.html', {'form': form})