import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import schedule
import os
import random
import sys

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
if not DISCORD_WEBHOOK_URL:
    print("ERROR: Debes definir la variable de entorno DISCORD_WEBHOOK_URL")
    sys.exit(1)

PRECIO_MINIMO = int(os.environ.get("PRECIO_MINIMO", 600))
PRECIO_MAXIMO = int(os.environ.get("PRECIO_MAXIMO", 1000))
ZONA_URL = os.environ.get(
    "ZONA_URL",
    "https://www.idealista.com/alquiler-viviendas/madrid/zona-sur/?ordenado-por=fecha-publicacion-desc"
)
BASE_DE_DATOS = "pisos.db"
REFRESH_TIME = int(os.environ.get("REFRESH_TIME", 15))

def get_free_proxies(n=8):
    url = "https://free-proxy-list.net"
    try:
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        proxies = []
        table = soup.find("table", class_="table")
        if not table:
            print("❌ No se encontró la tabla de proxies.")
            return []
        for row in table.tbody.find_all("tr")[:n]:
            cols = row.find_all("td")
            ip = cols[0].text.strip()
            port = cols[1].text.strip()
            https = cols[6].text.strip().lower()
            if https == "yes":
                proxies.append(f"https://{ip}:{port}")
        print("🔌 Proxies obtenidos:", proxies)
        return proxies
    except Exception as e:
        print("❌ No se pudieron obtener proxies:", e)
        return []


def setup_db():
    conn = sqlite3.connect(BASE_DE_DATOS)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pisos (
            id TEXT PRIMARY KEY,
            url TEXT,
            precio INTEGER,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def obtener_pisos():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
    }

    proxies_to_try = get_free_proxies(8)
    random.shuffle(proxies_to_try)
    response = None

    for proxy_url in proxies_to_try:
        proxies = {"http": proxy_url, "https": proxy_url}
        try:
            print(f"🌐 Probando proxy: {proxy_url}")
            response = requests.get(ZONA_URL, headers=headers, timeout=10, proxies=proxies)
            if response.status_code == 200 and len(response.text) > 1000:
                print(f"✅ Proxy funcionó: {proxy_url}")
                break
            else:
                print(f"⚠️ Proxy {proxy_url} respondió pero no parece válido.")
        except Exception as e:
            print(f"❌ Error con el proxy {proxy_url}: {e}")

    # Si no funcionó ningún proxy, intenta sin proxy
    if response is None or response.status_code != 200 or len(response.text) < 1000:
        print("🔄 Intentando sin proxy...")
        response = requests.get(ZONA_URL, headers=headers, timeout=10)

    print("📶 Estado HTTP:", response.status_code)
    print("📄 Longitud del HTML:", len(response.text))

    soup = BeautifulSoup(response.text, 'html.parser')
    items = soup.select("article.item")
    print("🏘️ Pisos encontrados en HTML:", len(items))

    pisos = []


    for item in items:
        try:
            id_piso = item.get("data-element-id")
            enlace_tag = item.select_one("a.item-link")
            url = "https://www.idealista.com" + enlace_tag.get("href")
            titulo = enlace_tag.get_text(strip=True)

            precio_tag = item.select_one(".item-price")
            precio_texto = precio_tag.get_text(strip=True).replace(".", "").replace("€", "").replace("/mes", "").replace(" ", "")
            precio = int(precio_texto)

            detalles = item.select(".item-detail")
            m2 = next((d.get_text(strip=True) for d in detalles if "m²" in d.get_text()), "N/A")
            ubicacion = titulo 

            tiempo_tag = item.select_one(".txt-highlight-red")
            publicado = tiempo_tag.get_text(strip=True) if tiempo_tag else "desconocido"

            img_tag = item.select_one("img")
            imagen_url = img_tag.get("src") if img_tag else ""

            if PRECIO_MINIMO <= precio <= PRECIO_MAXIMO:
                pisos.append({
                    "id": id_piso,
                    "url": url,
                    "precio": precio,
                    "m2": m2,
                    "ubicacion": ubicacion,
                    "publicado": publicado,
                    "titulo": titulo,
                    "imagenes": [imagen_url] if imagen_url else []
                })

        except Exception as e:
            print("❌ Error parseando piso:", e)
            continue

    print(f"✅ Pisos dentro del rango ({PRECIO_MINIMO}-{PRECIO_MAXIMO} €):", len(pisos))
    return pisos

def enviar_discord(piso):
    color = random.randint(0, 0xFFFFFF) 

    embeds = []

    principal_embed = {
        "title": piso["titulo"],
        "url": piso["url"],
        "description": f"**💰 Precio:** {piso['precio']} €\n**📐 Metros:** {piso['m2']}\n**📍 Ubicación:** {piso['ubicacion']}\n**⏱ Publicado:** {piso['publicado']}",
        "color": color
    }

    if piso["imagenes"]:
        principal_embed["thumbnail"] = {"url": piso["imagenes"][0]}

    embeds.append(principal_embed)

 
    for img_url in piso["imagenes"][1:]:
        embeds.append({
            "image": {"url": img_url},
            "color": color
        })

    payload = {"embeds": embeds}

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        print("📤 Enviado a Discord:", response.status_code)
        if response.status_code >= 400:
            print("⚠️ Respuesta Discord:", response.text)
    except Exception as e:
        print("❌ Error al enviar a Discord:", e)

def registrar_piso(piso):
    conn = sqlite3.connect(BASE_DE_DATOS)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO pisos (id, url, precio) VALUES (?, ?, ?)", (piso["id"], piso["url"], piso["precio"]))
        conn.commit()
        print("💾 Piso registrado en la base de datos:", piso["id"])
    except sqlite3.IntegrityError:
        print("⚠️ Piso ya registrado:", piso["id"])
    conn.close()

def registrar_y_enviar_nuevos(pisos):
    conn = sqlite3.connect(BASE_DE_DATOS)
    cursor = conn.cursor()
    nuevos = 0

    for piso in pisos:
        cursor.execute("SELECT id FROM pisos WHERE id = ?", (piso["id"],))
        if cursor.fetchone() is None:
            enviar_discord(piso)
            registrar_piso(piso)
            nuevos += 1
        else:
            print("⏭️ Piso ya conocido, no se envía:", piso["id"])

    conn.close()
    print(f"📬 Nuevos pisos enviados: {nuevos}")

def primera_ejecucion():
    print("🔰 Primera ejecución. Enviando los últimos 5 pisos...")
    pisos = obtener_pisos()
    filtrados = pisos[:5]
    for piso in filtrados:
        enviar_discord(piso)
        registrar_piso(piso)
    print("✅ Inicialización completada con los últimos 5 pisos.")

def tarea_periodica():
    print("\n⏱️ Ejecutando tarea periódica...")
    pisos = obtener_pisos()
    registrar_y_enviar_nuevos(pisos)


if __name__ == "__main__":
    setup_db()

    conn = sqlite3.connect(BASE_DE_DATOS)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pisos")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        primera_ejecucion()
    else:
        tarea_periodica()

    schedule.every(REFRESH_TIME).minutes.do(tarea_periodica)
    print(f"🚀 Scraper en marcha. Revisando cada {REFRESH_TIME} minutos...")

    while True:
        schedule.run_pending()
        time.sleep(1)