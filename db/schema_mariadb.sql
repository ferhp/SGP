-- Esquema de base de datos para MariaDB (motor InnoDB, utf8mb4).
-- La aplicación también crea las tablas automáticamente con SQLAlchemy al
-- arrancar; este script sirve para preparar el servidor y el usuario.

CREATE DATABASE IF NOT EXISTS gestion_proyectos
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_spanish_ci;

-- Usuario de la aplicación (cambiar la contraseña en producción):
CREATE USER IF NOT EXISTS 'gestion'@'%' IDENTIFIED BY 'gestion123';
GRANT ALL PRIVILEGES ON gestion_proyectos.* TO 'gestion'@'%';
FLUSH PRIVILEGES;

USE gestion_proyectos;

CREATE TABLE IF NOT EXISTS proyectos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  clave VARCHAR(20) NOT NULL UNIQUE,
  nombre VARCHAR(150) NOT NULL,
  tipo ENUM('Civil', 'Eléctrico') NOT NULL,
  cliente VARCHAR(150) NOT NULL,
  ubicacion VARCHAR(200),
  descripcion TEXT,
  fecha_inicio DATE NOT NULL,
  fecha_fin_prevista DATE NULL,
  presupuesto DECIMAL(14,2) DEFAULT 0,
  avance INT DEFAULT 0,
  estado ENUM('Planeación', 'En curso', 'Suspendido', 'Terminado')
    NOT NULL DEFAULT 'Planeación'
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS empleados (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(150) NOT NULL,
  puesto VARCHAR(100) NOT NULL,
  departamento ENUM('Obra civil', 'Obra eléctrica', 'Costos', 'Contabilidad',
                    'Recursos Humanos', 'Administración') NOT NULL,
  correo VARCHAR(150),
  telefono VARCHAR(30),
  salario_diario DECIMAL(10,2) DEFAULT 0,
  activo TINYINT(1) DEFAULT 1,
  proyecto_id INT NULL,
  CONSTRAINT fk_empleado_proyecto FOREIGN KEY (proyecto_id)
    REFERENCES proyectos(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Catálogo de proveedores (los costos lo usan mediante listbox).
CREATE TABLE IF NOT EXISTS proveedores (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(150) NOT NULL UNIQUE,
  rfc VARCHAR(13) DEFAULT '',
  telefono VARCHAR(30) DEFAULT '',
  correo VARCHAR(150) DEFAULT ''
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS costos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  proyecto_id INT NOT NULL,
  categoria ENUM('Materiales', 'Mano de obra', 'Maquinaria y equipo',
                 'Subcontratos', 'Indirectos') NOT NULL,
  concepto VARCHAR(200) NOT NULL,
  proveedor_id INT NULL,
  monto DECIMAL(14,2) NOT NULL,
  fecha DATE NOT NULL,
  CONSTRAINT fk_costo_proyecto FOREIGN KEY (proyecto_id)
    REFERENCES proyectos(id) ON DELETE CASCADE,
  CONSTRAINT fk_costo_proveedor FOREIGN KEY (proveedor_id)
    REFERENCES proveedores(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS movimientos_contables (
  id INT AUTO_INCREMENT PRIMARY KEY,
  proyecto_id INT NULL,
  tipo ENUM('Ingreso', 'Egreso') NOT NULL,
  cuenta ENUM('Bancos', 'Clientes', 'Proveedores', 'Anticipos de clientes',
              'Gastos de operación', 'Impuestos', 'Otros') NOT NULL,
  referencia VARCHAR(50),
  concepto VARCHAR(200) NOT NULL,
  monto DECIMAL(14,2) NOT NULL,
  fecha DATE NOT NULL,
  archivo_xml VARCHAR(255) NULL,
  archivo_pdf VARCHAR(255) NULL,
  CONSTRAINT fk_movimiento_proyecto FOREIGN KEY (proyecto_id)
    REFERENCES proyectos(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS recibos_nomina (
  id INT AUTO_INCREMENT PRIMARY KEY,
  empleado_id INT NOT NULL,
  periodo VARCHAR(30) NOT NULL,
  fecha_pago DATE NOT NULL,
  dias_trabajados INT NOT NULL,
  percepciones DECIMAL(12,2) NOT NULL,
  deducciones DECIMAL(12,2) NOT NULL,
  neto DECIMAL(12,2) NOT NULL,
  CONSTRAINT uq_recibo_empleado_periodo UNIQUE (empleado_id, periodo),
  CONSTRAINT fk_recibo_empleado FOREIGN KEY (empleado_id)
    REFERENCES empleados(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Usuarios autenticados por SSO (OpenID Connect).
CREATE TABLE IF NOT EXISTS usuarios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sub VARCHAR(255) NOT NULL UNIQUE,
  correo VARCHAR(150) NOT NULL UNIQUE,
  nombre VARCHAR(150) NOT NULL,
  apellido_paterno VARCHAR(80) DEFAULT '',
  apellido_materno VARCHAR(80) DEFAULT '',
  nss VARCHAR(15) DEFAULT '',
  curp VARCHAR(18) DEFAULT '',
  rfc VARCHAR(13) DEFAULT '',
  direccion VARCHAR(250) DEFAULT '',
  telefono VARCHAR(30) DEFAULT '',
  fecha_nacimiento DATE NULL,
  genero VARCHAR(20) DEFAULT '',
  fecha_ingreso DATE NULL,
  puesto VARCHAR(100) DEFAULT '',
  rol ENUM('Admin', 'Usuario') NOT NULL DEFAULT 'Usuario',
  departamento ENUM('Dirección', 'Proyectos', 'Costos', 'Contabilidad',
                    'Recursos Humanos', 'Nómina') NOT NULL DEFAULT 'Proyectos',
  activo TINYINT(1) DEFAULT 1,
  captura_costos TINYINT(1) DEFAULT 0,
  mfa_requerido TINYINT(1) DEFAULT 0,
  mfa_habilitado TINYINT(1) DEFAULT 0,
  mfa_secreto VARCHAR(64) NULL,
  ultimo_acceso DATETIME NULL
) ENGINE=InnoDB;
