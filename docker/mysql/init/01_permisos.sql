
-- Permisos para la base de pruebas de Django
GRANT ALL PRIVILEGES ON test_biblioteca.*
TO 'biblioteca_app'@'%';

-- Acceso de solo lectura al modelo del profesor
GRANT SELECT ON biblioteca_modelo.*
TO 'biblioteca_app'@'%';
