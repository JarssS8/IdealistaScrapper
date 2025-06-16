

# Lore Scrapper

Scrapea pisos de alquiler en Idealista para una zona y rango de precios, usando proxies gratuitos y enviando los resultados a un canal de Discord mediante webhook.

## Uso con Docker

1. Construye la imagen:
   ```sh
   docker build -t lore-scrapper .
   ```

2. Ejecuta el contenedor (webhook obligatorio, el resto opcional):
   ```sh
   docker run --rm \
     -e DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." \
     -e ZONA_URL="https://www.idealista.com/alquiler-viviendas/madrid/zona-sur/?ordenado-por=fecha-publicacion-desc" \
     -e PRECIO_MINIMO=600 \
     -e PRECIO_MAXIMO=1200 \
     -e REFRESH_TIME=1 \
     lore-scrapper
   ```

- Si no defines `ZONA_URL`, `PRECIO_MINIMO`, `PRECIO_MAXIMO` o `REFRESH_TIME`, se usan los valores por defecto.
- El webhook de Discord es obligatorio.

## Variables de entorno

- `DISCORD_WEBHOOK_URL` **(obligatorio)**
- `ZONA_URL` (opcional)
- `PRECIO_MINIMO` (opcional)
- `PRECIO_MAXIMO` (opcional)
- `REFRESH_TIME` (opcional, minutos)

## Requisitos

- Docker
- Un webhook de Discord válido

## Qué hace

- Obtiene proxies gratuitos de https://free-proxy-list.net
- Scrapea Idealista usando los proxies para evitar bloqueos
- Filtra pisos por precio
- Envía los nuevos pisos encontrados a Discord
- Guarda los pisos enviados en una base de datos local