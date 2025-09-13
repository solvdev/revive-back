from django.db import transaction
from accounts.models import Client, CustomUser
from django.contrib.auth.models import Group
from django.utils.text import slugify

@transaction.atomic
def generar_usuarios_para_clientes_activos():
    client_group, _ = Group.objects.get_or_create(name="client")

    clientes = Client.objects.filter(user__isnull=True, status="A")
    print(f"Procesando {clientes.count()} clientes activos sin usuario...")

    creados = 0
    for cliente in clientes.select_related(None):
        # Normaliza nombre y apellido
        fn = (cliente.first_name or "").strip()
        ln = (cliente.last_name or "").strip()

        # Generar username: inicial de nombre + primera palabra del apellido
        first_initial = (fn[0].lower() if fn else "x")
        last_word = (ln.lower().split()[0] if ln else "cliente")
        username_base = slugify(f"{first_initial}{last_word}") or "cliente"
        username = username_base

        # Evitar duplicados de username
        counter = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f"{username_base}{counter}"
            counter += 1

        # Crear usuario
        user = CustomUser.objects.create(
            username=username,
            email=(cliente.email or "").strip().lower(),
            is_enabled=True,
        )
        user.set_unusable_password()  # usa set_password(...) si quieres una temporal
        user.save()

        # Asignar grupo
        user.groups.add(client_group)

        # Asociar con cliente
        cliente.user = user
        cliente.save(update_fields=["user"])

        creados += 1
        print(f"✔ {cliente.full_name} -> {username}")

    print(f"\n✅ Proceso completado. Usuarios creados: {creados}/{clientes.count()}.")

# Ejecutar
generar_usuarios_para_clientes_activos()
