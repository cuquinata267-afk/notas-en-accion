# Puesta en marcha del pipeline

## 1. GitHub y Docker Hub

1. Crea un repositorio vacío en GitHub llamado `notas-en-accion` bajo `cuquinata267-afk`. El código local ya incluye un README. Puedes elegir la visibilidad que te pidan para entregar.
2. En Docker Hub crea `notas-en-accion-api` y `notas-en-accion-web` bajo tu usuario. Usa repositorios públicos para que la VM pueda descargar las imágenes directamente. Reutiliza el token de publicación del portafolio si tiene permiso de escritura en ambos repositorios.
3. En el repositorio nuevo abre **Settings → Secrets and variables → Actions**. Crea la variable `DOCKERHUB_USERNAME` y el secreto `DOCKERHUB_TOKEN`. Completa también los valores de la siguiente sección antes de activar `DEPLOY_ENABLED`.
4. Publica las ramas desde el repositorio local. Estos comandos suponen que `origin` apunta al repo nuevo y que el repo remoto todavía está vacío.

   ```powershell
   cd D:\ociportafolio\notas-en-accion
   git push -u origin main
   git push -u origin dev
   ```

5. En **Actions**, verifica las pruebas de `dev` y la publicación de las dos imágenes desde `main`. En `dev` verás **Pruebas de Notas en Acción**. Para publicar y desplegar, abre **Deploy OCI - Notas en Acción → Run workflow** y selecciona `main`. El trabajo **Desplegar en OCI** se ejecuta con `DEPLOY_ENABLED=true` después de que pasen las pruebas y se publiquen ambas imágenes.

## 2. OCI

Terraform provisiona una VCN, subred pública, gateway de internet, rutas, reglas de red y una VM Ubuntu 24.04 con IP pública. Puedes reutilizar la cuenta, el compartimento y el bucket privado del portafolio si das al usuario de API los permisos necesarios. El estado de Notas se guarda en `notas-en-accion/production.tfstate` en ese bucket.

Comprueba el shape y el OCID de la imagen en **Compute → Instances → tu VM del portafolio** si quieres repetir su combinación. El workflow del portafolio puede seleccionar una forma e imagen distintas de las variables iniciales. Notas usa directamente lo que configures en `OCI_SHAPE` y `OCI_UBUNTU_IMAGE_OCID`. `VM.Standard.A1.Flex` usa ARM64. Un shape x86 como `VM.Standard.E5.Flex` requiere Ubuntu 24.04 AMD64. Comprueba el cupo disponible y el costo de la segunda VM antes de activar el despliegue.

| Variables GitHub | Valor |
| --- | --- |
| `OCI_REGION`, `OCI_COMPARTMENT_OCID`, `OCI_AVAILABILITY_DOMAIN` | Copia los valores del portafolio si usamos la misma región y compartimento. Usa el nombre completo del availability domain. |
| `OCI_UBUNTU_IMAGE_OCID`, `OCI_SHAPE` | Imagen compatible y shape. El segundo puede omitirse para usar A1 Flex. |
| `OCI_NAMESPACE`, `OCI_STATE_BUCKET` | Reutiliza el namespace y el nombre de bucket del portafolio. |
| `SSH_PUBLIC_KEY`, `SSH_HOST_PUBLIC_KEY` | Claves públicas para acceso y para la identidad de la VM nueva. Usa los archivos de la tabla de abajo. |
| `DEPLOY_ENABLED` | `true` cuando Docker Hub, OCI, SSH y las cuentas estén configurados. |

| Secretos GitHub | Valor |
| --- | --- |
| `OCI_USER_OCID`, `OCI_TENANCY_OCID`, `OCI_FINGERPRINT`, `OCI_API_KEY` | Reutiliza la configuración de la misma clave de API de OCI y el PEM original asociado. |
| `SSH_PRIVATE_KEY`, `SSH_HOST_PRIVATE_KEY` | Claves privadas que corresponden a los pares SSH. |
| `NOTES_PASSWORD_1`, `NOTES_PASSWORD_2` | Contraseñas para `demo1` y `demo2`. Genera dos valores con `python -c "import secrets; print(secrets.token_urlsafe(24))"`. |

En este PC se verificó el par de acceso `portfolio_access` y se preparó el par `notas-host` para la identidad de la nueva VM. Copia el contenido completo de cada archivo en el campo que corresponde del repo nuevo.

| Campo en GitHub | Tipo | Archivo en este PC |
| --- | --- | --- |
| `SSH_PUBLIC_KEY` | Variable | `%USERPROFILE%\.ssh\portfolio_access.pub` |
| `SSH_PRIVATE_KEY` | Secreto | `%USERPROFILE%\.ssh\portfolio_access` |
| `SSH_HOST_PUBLIC_KEY` | Variable | `D:\ociportafolio\.tools\notas-ssh\notas-host.pub` |
| `SSH_HOST_PRIVATE_KEY` | Secreto | `D:\ociportafolio\.tools\notas-ssh\notas-host` |

Los secretos del portafolio se deben cargar en el repo nuevo con los valores originales, desde tus archivos o tu gestor de secretos. GitHub no vuelve a mostrar su contenido guardado. Guarda las privadas fuera del código y conserva el mismo par `notas-host` después de crear la VM. El runner comprueba que cada privada corresponde con su pública antes de aplicar Terraform. Protege el acceso al bucket porque el estado contiene configuración sensible de la instancia.

El pipeline ajusta la regla de SSH al IP del runner. Ansible instala Docker, Compose, Git, Nginx e iptables, y deja el puerto de la app detrás de Nginx. SQLite se conserva en el volumen `notas-en-accion_notes_data` de la VM. El primer arranque crea las tablas y las dos cuentas.

## 3. Cloudflare

Primero valida por IP con datos de demo. Para habilitar HTTPS, agrega la zona de un dominio que controlas a Cloudflare y define `NOTES_DOMAIN` y `CLOUDFLARE_ZONE_ID`. Agrega los secretos `CLOUDFLARE_API_TOKEN` con permiso de edición DNS en esa zona, `CLOUDFLARE_ORIGIN_CERT` y `CLOUDFLARE_ORIGIN_KEY`. El certificado debe incluir tu subdominio.

Configura SSL/TLS **Full (strict)** en Cloudflare y vuelve a ejecutar el workflow de `main`. Ansible instalará el certificado y actualizará el registro `A` con proxy. El resumen de GitHub Actions muestra la URL y el workflow valida `/` y `/api/health`.
