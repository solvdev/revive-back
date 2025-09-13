# Revive Pilates Backend

Este es el backend de Django para el sistema de gestión de Revive Pilates Studio.

## Estructura del Proyecto

- **accounts**: Gestión de usuarios y clientes
- **studio**: Gestión de clases, horarios, membresías y reservas
- **finance**: Módulo de finanzas (pendiente de implementación)
- **inventory**: Módulo de inventario (pendiente de implementación)

## Configuración de Base de Datos

- **Host**: revive-db.c7okeymccfwd.us-east-2.rds.amazonaws.com
- **Puerto**: 5432
- **Base de datos**: revive
- **Usuario**: reviveadmin
- **Contraseña**: revive2025!

## Instalación

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Configurar variables de entorno (opcional):
```bash
# Crear archivo .env con las configuraciones necesarias
```

3. Ejecutar migraciones:
```bash
python manage.py makemigrations
python manage.py migrate
```

4. Crear superusuario:
```bash
python manage.py createsuperuser
```

5. Ejecutar servidor de desarrollo:
```bash
python manage.py runserver
```

## Características

- Sistema de autenticación JWT
- Soporte multi-sede
- Gestión de clientes y usuarios
- Sistema de reservas y clases
- Gestión de membresías y promociones
- Sistema de pagos
- API REST completa

## Tecnologías

- Django 5.1.7
- Django REST Framework
- PostgreSQL
- JWT Authentication
- CORS Headers
- Mailjet para emails
