# Datos de ejemplo: se insertan solo cuando la base de datos está vacía,
# para que la aplicación pueda explorarse desde el primer arranque.
from datetime import date
from decimal import Decimal

from models import db_session
from models.contabilidad import MovimientoContable
from models.costo import Costo
from models.empleado import Empleado
from models.nomina import ReciboNomina
from models.proveedor import Proveedor
from models.proyecto import Proyecto
from models.usuario import Usuario


def sembrar_si_vacio():
    _sembrar_usuarios()
    if db_session.query(Proyecto).first() or db_session.query(Empleado).first():
        return


def _sembrar_usuarios():
    # Cuenta administradora inicial para el modo de desarrollo del SSO;
    # con un IdP real, los usuarios se crean solos al iniciar sesión.
    if db_session.query(Usuario).first():
        return
    db_session.add(Usuario(
        sub="dev|admin@constructora.mx", correo="admin@constructora.mx",
        nombre="Administrador", rol="Admin", departamento="Dirección",
    ))
    db_session.commit()

    p1 = Proyecto(
        clave="CIV-001", nombre="Puente vehicular Río Blanco", tipo="Civil",
        cliente="Gobierno Municipal de Orizaba", ubicacion="Orizaba, Veracruz",
        descripcion="Puente vehicular de 120 m con dos carriles y banquetas peatonales.",
        fecha_inicio=date(2026, 2, 10), fecha_fin_prevista=date(2026, 12, 15),
        presupuesto=Decimal("18500000"), avance=45, estado="En curso",
    )
    p2 = Proyecto(
        clave="CIV-002", nombre="Nave industrial Parque Sur", tipo="Civil",
        cliente="Logística del Golfo SA de CV", ubicacion="Córdoba, Veracruz",
        descripcion="Nave industrial de 4,800 m² con oficinas administrativas.",
        fecha_inicio=date(2026, 5, 4), fecha_fin_prevista=date(2027, 3, 31),
        presupuesto=Decimal("32000000"), avance=12, estado="En curso",
    )
    p3 = Proyecto(
        clave="ELE-001", nombre="Subestación eléctrica 115 kV Norte", tipo="Eléctrico",
        cliente="CFE Distribución", ubicacion="Xalapa, Veracruz",
        descripcion="Subestación de distribución 115/13.8 kV con dos transformadores.",
        fecha_inicio=date(2026, 1, 12), fecha_fin_prevista=date(2026, 10, 30),
        presupuesto=Decimal("24700000"), avance=68, estado="En curso",
    )
    p4 = Proyecto(
        clave="ELE-002", nombre="Electrificación fraccionamiento Los Álamos",
        tipo="Eléctrico", cliente="Inmobiliaria Los Álamos",
        ubicacion="Boca del Río, Veracruz",
        descripcion="Red de media y baja tensión, alumbrado público y acometidas.",
        fecha_inicio=date(2026, 8, 1), fecha_fin_prevista=date(2027, 1, 20),
        presupuesto=Decimal("7800000"), avance=0, estado="Planeación",
    )
    db_session.add_all([p1, p2, p3, p4])
    db_session.flush()

    nombres_proveedores = ("Cemex", "Gruas del Centro", "Aceros Córdoba",
                           "Terracerías Golfo", "Prolec GE",
                           "Constructora Xalapa", "LAPEM")
    proveedores = {}
    for nombre in nombres_proveedores:
        proveedor = db_session.query(Proveedor).filter_by(nombre=nombre).first()
        if not proveedor:
            proveedor = Proveedor(nombre=nombre)
            db_session.add(proveedor)
        proveedores[nombre] = proveedor
    db_session.flush()

    empleados = [
        Empleado(nombre="Laura Méndez Ríos", puesto="Residente de obra",
                 departamento="Obra civil", correo="laura.mendez@constructora.mx",
                 telefono="272-555-0101", salario_diario=Decimal("950"),
                 proyecto_id=p1.id),
        Empleado(nombre="Carlos Gutiérrez Peña", puesto="Ingeniero eléctrico",
                 departamento="Obra eléctrica", correo="carlos.gutierrez@constructora.mx",
                 telefono="228-555-0102", salario_diario=Decimal("1050"),
                 proyecto_id=p3.id),
        Empleado(nombre="Ana Sofía Herrera", puesto="Analista de costos",
                 departamento="Costos", correo="ana.herrera@constructora.mx",
                 telefono="271-555-0103", salario_diario=Decimal("720")),
        Empleado(nombre="Jorge Luna Castillo", puesto="Contador general",
                 departamento="Contabilidad", correo="jorge.luna@constructora.mx",
                 telefono="229-555-0104", salario_diario=Decimal("880")),
        Empleado(nombre="María Fernanda Solís", puesto="Jefa de Recursos Humanos",
                 departamento="Recursos Humanos", correo="maria.solis@constructora.mx",
                 telefono="272-555-0105", salario_diario=Decimal("800")),
        Empleado(nombre="Pedro Ramírez Ortega", puesto="Cabo de electricistas",
                 departamento="Obra eléctrica", correo="pedro.ramirez@constructora.mx",
                 telefono="228-555-0106", salario_diario=Decimal("560"),
                 proyecto_id=p3.id),
        Empleado(nombre="Rosa Elena Cabrera", puesto="Auxiliar contable",
                 departamento="Contabilidad", correo="rosa.cabrera@constructora.mx",
                 telefono="229-555-0107", salario_diario=Decimal("480")),
        Empleado(nombre="Miguel Ángel Torres", puesto="Maestro albañil",
                 departamento="Obra civil", correo="", telefono="272-555-0108",
                 salario_diario=Decimal("520"), proyecto_id=p1.id),
    ]
    db_session.add_all(empleados)
    db_session.flush()

    db_session.add_all([
        Costo(proyecto_id=p1.id, categoria="Materiales", concepto="Concreto premezclado f'c 300",
              proveedor=proveedores["Cemex"], monto=Decimal("1250000"), fecha=date(2026, 4, 18)),
        Costo(proyecto_id=p1.id, categoria="Maquinaria y equipo", concepto="Renta de grúa 90 t (2 meses)",
              proveedor=proveedores["Gruas del Centro"], monto=Decimal("640000"), fecha=date(2026, 5, 2)),
        Costo(proyecto_id=p1.id, categoria="Mano de obra", concepto="Destajos cimentación estribos",
              monto=Decimal("870000"), fecha=date(2026, 6, 15)),
        Costo(proyecto_id=p2.id, categoria="Materiales", concepto="Acero estructural A-36 (180 t)",
              proveedor=proveedores["Aceros Córdoba"], monto=Decimal("3150000"), fecha=date(2026, 6, 20)),
        Costo(proyecto_id=p2.id, categoria="Subcontratos", concepto="Movimiento de tierras y plataformas",
              proveedor=proveedores["Terracerías Golfo"], monto=Decimal("1420000"), fecha=date(2026, 5, 28)),
        Costo(proyecto_id=p3.id, categoria="Materiales", concepto="Transformador 30 MVA 115/13.8 kV",
              proveedor=proveedores["Prolec GE"], monto=Decimal("8900000"), fecha=date(2026, 3, 10)),
        Costo(proyecto_id=p3.id, categoria="Subcontratos", concepto="Obra civil de bases y trincheras",
              proveedor=proveedores["Constructora Xalapa"], monto=Decimal("2100000"), fecha=date(2026, 4, 5)),
        Costo(proyecto_id=p3.id, categoria="Mano de obra", concepto="Montaje electromecánico",
              monto=Decimal("1750000"), fecha=date(2026, 7, 1)),
        Costo(proyecto_id=p3.id, categoria="Indirectos", concepto="Supervisión y pruebas de laboratorio",
              proveedor=proveedores["LAPEM"], monto=Decimal("430000"), fecha=date(2026, 7, 22)),
    ])

    db_session.add_all([
        MovimientoContable(proyecto_id=p1.id, tipo="Ingreso", cuenta="Anticipos de clientes",
                           referencia="F-2026-014", concepto="Anticipo 30% puente Río Blanco",
                           monto=Decimal("5550000"), fecha=date(2026, 2, 20)),
        MovimientoContable(proyecto_id=p1.id, tipo="Ingreso", cuenta="Clientes",
                           referencia="EST-03", concepto="Estimación 3 de obra ejecutada",
                           monto=Decimal("2480000"), fecha=date(2026, 6, 30)),
        MovimientoContable(proyecto_id=p1.id, tipo="Egreso", cuenta="Proveedores",
                           referencia="F-8841", concepto="Pago Cemex concreto",
                           monto=Decimal("1250000"), fecha=date(2026, 5, 5)),
        MovimientoContable(proyecto_id=p3.id, tipo="Ingreso", cuenta="Anticipos de clientes",
                           referencia="F-2026-002", concepto="Anticipo subestación Norte",
                           monto=Decimal("9880000"), fecha=date(2026, 1, 25)),
        MovimientoContable(proyecto_id=p3.id, tipo="Egreso", cuenta="Proveedores",
                           referencia="F-5520", concepto="Pago transformador Prolec",
                           monto=Decimal("8900000"), fecha=date(2026, 4, 12)),
        MovimientoContable(proyecto_id=None, tipo="Egreso", cuenta="Gastos de operación",
                           referencia="REN-08", concepto="Renta de oficinas centrales agosto",
                           monto=Decimal("85000"), fecha=date(2026, 8, 1)),
        MovimientoContable(proyecto_id=None, tipo="Egreso", cuenta="Impuestos",
                           referencia="SAT-07", concepto="Pago provisional ISR julio",
                           monto=Decimal("310000"), fecha=date(2026, 8, 17)),
    ])

    # Nómina de la primera quincena de agosto para toda la plantilla.
    for empleado in empleados:
        percepciones = empleado.salario_diario * 15
        deducciones = (percepciones * Decimal("0.12")).quantize(Decimal("0.01"))
        db_session.add(ReciboNomina(
            empleado_id=empleado.id, periodo="2026-08 Q1",
            fecha_pago=date(2026, 8, 15), dias_trabajados=15,
            percepciones=percepciones, deducciones=deducciones,
            neto=percepciones - deducciones,
        ))

    db_session.commit()
    print("[SEED] Datos de ejemplo insertados.")
