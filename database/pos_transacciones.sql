CREATE DATABASE IF NOT EXISTS pos_transacciones CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE pos_transacciones;

-- Tabla de productos
CREATE TABLE productos (
    clave VARCHAR(20) PRIMARY KEY,
    descripcion VARCHAR(100) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL,
    CONSTRAINT chk_stock_no_negativo CHECK (stock >= 0)
) ENGINE=InnoDB;

-- Tabla de ventas
CREATE TABLE ventas (
    folio INT AUTO_INCREMENT PRIMARY KEY,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    empleado VARCHAR(80) NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    iva DECIMAL(10, 2) NOT NULL,
    total DECIMAL(10, 2) NOT NULL,
    cadena_qr VARCHAR(255) NULL
) ENGINE=InnoDB;

-- Tabla de detalles de venta
CREATE TABLE detalles_venta (
    id_detalle INT AUTO_INCREMENT PRIMARY KEY,
    folio_venta INT NOT NULL,
    clave_producto VARCHAR(20) NOT NULL,
    cantidad INT NOT NULL,
    precio DECIMAL(10, 2) NOT NULL,
    importe DECIMAL(10, 2) NOT NULL,
    CONSTRAINT fk_venta FOREIGN KEY (folio_venta) REFERENCES ventas(folio) ON DELETE CASCADE,
    CONSTRAINT fk_producto FOREIGN KEY (clave_producto) REFERENCES productos(clave)
) ENGINE=InnoDB;

-- Productos iniciales
INSERT INTO productos (clave, descripcion, precio, stock) VALUES
('7622202825682', 'COCA 600', 23.00, 15),
('7501295600614', 'DORITOS 150G', 20.00, 5),
('7500810049686', 'GALLETAS EMPERADOR', 18.00, 10),
('7501000111201', 'GANSITO MARINELA 50G', 19.00, 2);

CREATE USER IF NOT EXISTS 'pos_app'@'localhost' IDENTIFIED BY 'pos1234';
GRANT SELECT, INSERT, UPDATE, DELETE ON pos_transacciones.* TO 'pos_app'@'localhost';
FLUSH PRIVILEGES;
