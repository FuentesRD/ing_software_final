from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    # CU-04 / CU-05: todos los usuarios
    path("", views.BuscarLibrosView.as_view(), name="buscar"),
    path("libros/<int:pk>/", views.DetalleLibroView.as_view(), name="detalle"),
    # CU-17: libros (bibliotecario)
    path("libros/nuevo/", views.CrearLibroView.as_view(), name="libro_crear"),
    path(
        "libros/<int:pk>/editar/",
        views.EditarLibroView.as_view(),
        name="libro_editar",
    ),
    path("libros/<int:pk>/baja/", views.BajaLibroView.as_view(), name="libro_baja"),
    # CU-18: ejemplares (bibliotecario)
    path(
        "libros/<int:libro_pk>/ejemplares/nuevo/",
        views.CrearEjemplarView.as_view(),
        name="ejemplar_crear",
    ),
    path(
        "ejemplares/<int:pk>/editar/",
        views.EditarEjemplarView.as_view(),
        name="ejemplar_editar",
    ),
    # CU-19: autores, editoriales y categorías (bibliotecario)
    path("autores/", views.AutorListaView.as_view(), name="autor_lista"),
    path("autores/nuevo/", views.AutorCrearView.as_view(), name="autor_crear"),
    path(
        "autores/<int:pk>/editar/",
        views.AutorEditarView.as_view(),
        name="autor_editar",
    ),
    path(
        "autores/<int:pk>/eliminar/",
        views.AutorEliminarView.as_view(),
        name="autor_eliminar",
    ),
    path("editoriales/", views.EditorialListaView.as_view(), name="editorial_lista"),
    path(
        "editoriales/nueva/",
        views.EditorialCrearView.as_view(),
        name="editorial_crear",
    ),
    path(
        "editoriales/<int:pk>/editar/",
        views.EditorialEditarView.as_view(),
        name="editorial_editar",
    ),
    path(
        "editoriales/<int:pk>/eliminar/",
        views.EditorialEliminarView.as_view(),
        name="editorial_eliminar",
    ),
    path("categorias/", views.CategoriaListaView.as_view(), name="categoria_lista"),
    path(
        "categorias/nueva/",
        views.CategoriaCrearView.as_view(),
        name="categoria_crear",
    ),
    path(
        "categorias/<int:pk>/editar/",
        views.CategoriaEditarView.as_view(),
        name="categoria_editar",
    ),
    path(
        "categorias/<int:pk>/eliminar/",
        views.CategoriaEliminarView.as_view(),
        name="categoria_eliminar",
    ),
    # CU-16 / CU-33: sugerencias
    path("sugerir/", views.SugerirLibroView.as_view(), name="sugerir"),
    path(
        "sugerencias/",
        views.SugerenciasListaView.as_view(),
        name="sugerencias_lista",
    ),
    path(
        "sugerencias/<int:pk>/responder/",
        views.ResponderSugerenciaView.as_view(),
        name="sugerencia_responder",
    ),
]