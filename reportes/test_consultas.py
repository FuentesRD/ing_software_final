from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.models import Categoria, Editorial, Ejemplar, Libro
from cuentas.models import Usuario
from multas.models import Multa, Pago
from prestamos.models import Prestamo

from . import services


class ConsultasReportesTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.ayer = self.hoy - timedelta(days=1)
        self.fecha = timezone.make_aware(
            datetime.combine(self.ayer, datetime.min.time())
        )

        self.usuario = Usuario.objects.create_user(
            username="lector_reportes",
            email="lector.reportes@example.com",
            tipo_usuario="ESTUDIANTE",
        )
        self.bibliotecario = Usuario.objects.create_user(
            username="encargado_reportes",
            email="encargado.reportes@example.com",
            tipo_usuario="BIBLIOTECARIO",
        )
        categoria = Categoria.objects.create(nombre="Pruebas")
        editorial = Editorial.objects.create(
            nombre="Editorial de pruebas",
        )
        self.libro = Libro.objects.create(
            titulo="Libro de pruebas",
            isbn="9780132350884",
            categoria=categoria,
            editorial=editorial,
        )
        self.ejemplar = Ejemplar.objects.create(
            libro=self.libro,
            codigo_inventario="REP-001",
        )
        self.prestamo = Prestamo.objects.create(
            usuario=self.usuario,
            ejemplar=self.ejemplar,
            estado="ACTIVO",
            fecha_solicitud=self.fecha,
            fecha_prestamo=self.fecha,
            fecha_vencimiento=self.ayer,
        )
        self.multa = Multa.objects.create(
            usuario=self.usuario,
            prestamo=self.prestamo,
            motivo="RETRASO",
            monto=Decimal("100.00"),
            estado="PENDIENTE",
            fecha_generacion=self.fecha,
        )
        self.pago = Pago.objects.create(
            multa=self.multa,
            monto=Decimal("30.00"),
            metodo="EFECTIVO",
            folio_recibo="REP-PAGO-001",
            fecha_pago=self.fecha,
            registrado_por=self.bibliotecario,
        )

    def test_prestamos_incluye_ambos_limites_del_periodo(self):
        resultado = services.prestamos_por_periodo(
            self.ayer, self.ayer,
        )

        self.assertEqual(list(resultado), [self.prestamo])
        self.assertFalse(
            services.prestamos_por_periodo(
                self.hoy, self.hoy,
            ).exists()
        )

    def test_prestamos_excluye_solicitudes_sin_entrega(self):
        self.prestamo.fecha_prestamo = None
        self.prestamo.estado = "SOLICITADO"
        self.prestamo.save()

        self.assertFalse(services.prestamos_por_periodo().exists())

    def test_libros_agrupa_solicitudes_por_titulo(self):
        otro_ejemplar = Ejemplar.objects.create(
            libro=self.libro,
            codigo_inventario="REP-002",
        )
        Prestamo.objects.create(
            usuario=self.usuario,
            ejemplar=otro_ejemplar,
            estado="CANCELADO",
            fecha_solicitud=self.fecha,
        )

        resultado = list(
            services.libros_mas_solicitados(self.ayer, self.ayer)
        )

        self.assertEqual(len(resultado), 1)
        self.assertEqual(
            resultado[0]["ejemplar__libro_id"],
            self.libro.pk,
        )
        self.assertEqual(resultado[0]["total_solicitudes"], 2)
        self.assertFalse(
            services.libros_mas_solicitados(
                self.hoy, self.hoy,
            ).exists()
        )

    def test_vencidos_incluye_activo_con_fecha_pasada(self):
        resultado = services.prestamos_vencidos(
            self.ayer, self.ayer,
        )

        self.assertEqual(list(resultado), [self.prestamo])

        self.prestamo.fecha_vencimiento = self.hoy
        self.prestamo.save()

        self.assertFalse(services.prestamos_vencidos().exists())

    def test_vencidos_excluye_prestamo_devuelto(self):
        self.prestamo.estado = "DEVUELTO"
        self.prestamo.fecha_devolucion = timezone.now()
        self.prestamo.save()

        self.assertFalse(services.prestamos_vencidos().exists())

    def test_cobradas_incluye_abonos_por_fecha_de_pago(self):
        resultado = services.multas_cobradas(
            self.ayer, self.ayer,
        )

        self.assertEqual(list(resultado), [self.pago])
        self.assertEqual(resultado[0].monto, Decimal("30.00"))
        self.assertFalse(
            services.multas_cobradas(self.hoy, self.hoy).exists()
        )

    def test_pendientes_descuenta_abonos(self):
        resultado = services.multas_pendientes(
            self.ayer, self.ayer,
        ).get()

        self.assertEqual(resultado.total_pagado, Decimal("30.00"))
        self.assertEqual(
            resultado.saldo_pendiente,
            Decimal("70.00"),
        )
        self.assertFalse(
            services.multas_pendientes(
                self.hoy, self.hoy,
            ).exists()
        )

    def test_pendientes_excluye_condonadas_y_pagadas(self):
        for estado in ("CONDONADA", "PAGADA"):
            with self.subTest(estado=estado):
                self.multa.estado = estado
                self.multa.save()

                self.assertFalse(
                    services.multas_pendientes().exists()
                )

    def test_pendientes_excluye_saldo_cero(self):
        Pago.objects.create(
            multa=self.multa,
            monto=Decimal("70.00"),
            metodo="EFECTIVO",
            folio_recibo="REP-PAGO-002",
            registrado_por=self.bibliotecario,
        )

        self.assertFalse(services.multas_pendientes().exists())

    def test_panel_muestra_datos_y_totales(self):
        self.client.force_login(self.bibliotecario)

        respuesta = self.client.get(reverse("reportes:panel"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Libro de pruebas")
        self.assertContains(respuesta, "REP-PAGO-001")
        self.assertEqual(
            respuesta.context["total_cobrado"],
            Decimal("30.00"),
        )
        self.assertEqual(
            respuesta.context["total_pendiente"],
            Decimal("70.00"),
        )

    def test_panel_rechaza_periodo_invertido(self):
        self.client.force_login(self.bibliotecario)

        respuesta = self.client.get(
            reverse("reportes:panel"),
            {
                "fecha_inicio": self.hoy.isoformat(),
                "fecha_fin": self.ayer.isoformat(),
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "La fecha final debe ser igual o posterior a la inicial.",
        )
        self.assertNotIn("prestamos", respuesta.context)