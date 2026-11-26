"""Comando procesar_vencimientos: CU-34, CU-35 y CU-36 (reloj del sistema)."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from notificaciones.models import Notificacion
from prestamos.models import Prestamo, Reserva

from .utilidades import crear_ejemplar, crear_libro, crear_usuario, estado_de


class ProcesarVencimientosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lector = crear_usuario("a1")
        cls.otro = crear_usuario("a2")
        cls.libro = crear_libro()

    def correr(self, *args):
        salida = StringIO()
        call_command("procesar_vencimientos", *args, stdout=salida)
        return salida.getvalue()

    def prestamo(self, estado, codigo, ejemplar_estado="PRESTADO", **campos):
        return Prestamo.objects.create(
            usuario=self.lector,
            ejemplar=crear_ejemplar(self.libro, codigo, estado=ejemplar_estado),
            estado=estado,
            **campos,
        )

    def test_cu34_marca_vencidos_solo_los_que_ya_pasaron(self):
        hoy = timezone.localdate()
        vencido = self.prestamo("ACTIVO", "EJ-1", fecha_vencimiento=hoy - timedelta(days=1))
        vence_hoy = self.prestamo("ACTIVO", "EJ-2", fecha_vencimiento=hoy)

        salida = self.correr()

        vencido.refresh_from_db()
        vence_hoy.refresh_from_db()
        self.assertEqual(vencido.estado, Prestamo.Estado.VENCIDO)
        self.assertEqual(vence_hoy.estado, Prestamo.Estado.ACTIVO)
        self.assertTrue(Notificacion.objects.filter(usuario=self.lector, tipo="VENCIDO").exists())
        self.assertIn("Préstamos vencidos: 1", salida)

    def test_cu35_expira_solicitud_no_recogida_y_libera_el_ejemplar(self):
        solicitud = self.prestamo(
            "SOLICITADO", "EJ-1", ejemplar_estado="RESERVADO",
            fecha_limite_recoger=timezone.now() - timedelta(hours=1),
        )
        a_tiempo = self.prestamo(
            "SOLICITADO", "EJ-2", ejemplar_estado="RESERVADO",
            fecha_limite_recoger=timezone.now() + timedelta(hours=10),
        )

        self.correr()

        solicitud.refresh_from_db()
        a_tiempo.refresh_from_db()
        self.assertEqual(solicitud.estado, Prestamo.Estado.EXPIRADO)
        self.assertEqual(estado_de(solicitud.ejemplar), "DISPONIBLE")
        self.assertEqual(a_tiempo.estado, Prestamo.Estado.SOLICITADO)
        self.assertEqual(estado_de(a_tiempo.ejemplar), "RESERVADO")

    def test_cu35_reserva_expirada_pasa_el_ejemplar_al_siguiente_en_la_cola(self):
        ejemplar = crear_ejemplar(self.libro, "EJ-R", estado="RESERVADO")
        vieja = Reserva.objects.create(
            usuario=self.lector, libro=self.libro, estado="DISPONIBLE",
            ejemplar_asignado=ejemplar, fecha_expiracion=timezone.now() - timedelta(minutes=1),
            fecha_reserva=timezone.now() - timedelta(days=3),
        )
        siguiente = Reserva.objects.create(usuario=self.otro, libro=self.libro)

        salida = self.correr()

        vieja.refresh_from_db()
        siguiente.refresh_from_db()
        self.assertEqual(vieja.estado, Reserva.Estado.EXPIRADA)
        self.assertEqual(siguiente.estado, Reserva.Estado.DISPONIBLE)
        self.assertEqual(siguiente.ejemplar_asignado, ejemplar)
        self.assertEqual(estado_de(ejemplar), "RESERVADO")
        self.assertIn("Reservas expiradas: 1", salida)

    def test_cu36_recordatorio_una_sola_vez_por_dia(self):
        hoy = timezone.localdate()
        self.prestamo("ACTIVO", "EJ-1", fecha_vencimiento=hoy + timedelta(days=1))
        self.prestamo("ACTIVO", "EJ-2", fecha_vencimiento=hoy + timedelta(days=5))

        self.correr()
        self.correr()

        self.assertEqual(Notificacion.objects.filter(tipo="VENCE_PRONTO").count(), 1)

    def test_cu36_dias_de_aviso_configurables(self):
        self.prestamo("ACTIVO", "EJ-1", fecha_vencimiento=timezone.localdate() + timedelta(days=3))

        salida = self.correr("--dias-aviso", "3")

        self.assertIn("Recordatorios enviados: 1", salida)
