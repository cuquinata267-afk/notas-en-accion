# Puesta en marcha del pipeline

## 1. GitHub y Docker Hub

1. Crea un repositorio vacío en GitHub llamado `notas-en-accion` bajo `cuquinata267-afk`. El código local ya incluye un README. Puedes elegir la visibilidad que te pidan para entregar.
2. Desde el repositorio local, agrega el remoto nuevo y publica las ramas. Estos comandos suponen que el repo remoto todavía está vacío.

   ```powershell
   git remote add origin https://github.com/cuquinata267-afk/notas-en-accion.git
   git push -u origin main
   git push -u origin dev
   ```

3. En Docker Hub crea `notas-en-accion-api` y `notas-en-accion-web` bajo tu usuario. Ambos pueden ser públicos para que la VM descargue las imágenes directamente. Usa un token de Docker Hub con permiso de publicación.
4. En GitHub abre **Settings → Secrets and variables → Actions**. Crea la variable `DOCKERHUB_USERNAME` y el secreto `DOCKERHUB_TOKEN`. Ejecuta el workflow de `main` para verificar las imágenes etiquetadas con el SHA del commit.

## 2. OCI

Terraform provisiona una VCN, subred pública, gateway de internet, rutas, reglas de red y una VM Ubuntu 24.04 con IP pública. Este proyecto usa `notas-en-accion/production.tfstate` en el bucket OCI que configures. El bucket debe ser privado y la cuenta de Terraform debe tener permiso sobre él y sobre el compartimento. Esa clave separa el estado del portafolio previo.

Configura el OCID de una imagen de **Ubuntu 24.04** compatible con tu shape y región. `VM.Standard.A1.Flex` usa ARM64 y es el valor predeterminado. Si usas un shape x86 disponible para tu cuenta, selecciona una imagen AMD64 y revisa sus límites y costos antes de activar el despliegue.

| Variables GitHub | Valor |
| --- | --- |
| `OCI_REGION`, `OCI_COMPARTMENT_OCID`, `OCI_AVAILABILITY_DOMAIN` | Región, compartimento y nombre completo del availability domain. |
| `OCI_UBUNTU_IMAGE_OCID`, `OCI_SHAPE` | Imagen compatible y shape. El segundo puede omitirse para usar A1 Flex. |
| `OCI_NAMESPACE`, `OCI_STATE_BUCKET` | Namespace y bucket de Object Storage. |
| `SSH_PUBLIC_KEY`, `SSH_HOST_PUBLIC_KEY` | Claves públicas de los pares de acceso e identidad del servidor. |
| `DEPLOY_ENABLED` | `true` cuando Docker Hub, OCI, SSH y las cuentas estén configurados. |

| Secretos GitHub | Valor |
| --- | --- |
| `OCI_USER_OCID`, `OCI_TENANCY_OCID`, `OCI_FINGERPRINT`, `OCI_API_KEY` | Datos de la clave API de OCI y su PEM privado. |
| `SSH_PRIVATE_KEY`, `SSH_HOST_PRIVATE_KEY` | Claves privadas que corresponden a los pares SSH. |
| `NOTES_PASSWORD_1`, `NOTES_PASSWORD_2` | Contraseñas para `demo1` y `demo2`. Genera dos valores con `python -c "import secrets; print(secrets.token_urlsafe(24))"`. |

Crea dos pares Ed25519 para la automatización, uno de acceso y otro de identidad del servidor. Guarda ambos fuera del repo. Cuando `ssh-keygen` pida una passphrase, pulsa Enter para que el runner pueda usar esas llaves dedicadas. En el runner se comprueba que cada clave privada corresponda a su pública antes de aplicar Terraform. Restringe el acceso al estado remoto porque contiene la configuración sensible de la instancia.

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE/.ssh/notas-access"
ssh-keygen -t ed25519 -f "$env:USERPROFILE/.ssh/notas-host"
```

El pipeline ajusta la regla de SSH al IP del runner. Ansible instala Docker, Compose, Git, Nginx e iptables, y deja el puerto de la app detrás de Nginx. SQLite se conserva en el volumen `notas-en-accion_notes_data` de la VM. El primer arranque crea las tablas y las dos cuentas.

## 3. Cloudflare

Primero valida por IP con datos de demo. Para habilitar HTTPS, agrega la zona de un dominio que controlas a Cloudflare y define `NOTES_DOMAIN` y `CLOUDFLARE_ZONE_ID`. Agrega los secretos `CLOUDFLARE_API_TOKEN` con permiso de edición DNS en esa zona, `CLOUDFLARE_ORIGIN_CERT` y `CLOUDFLARE_ORIGIN_KEY`. El certificado debe incluir tu subdominio.

Configura SSL/TLS **Full (strict)** en Cloudflare y vuelve a ejecutar el workflow de `main`. Ansible instalará el certificado y actualizará el registro `A` con proxy. El resumen de GitHub Actions muestra la URL y el workflow valida `/` y `/api/health`.
