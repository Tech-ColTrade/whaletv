"""
Cliente de prueba para la WhaleTV / Zeasn Device Lock Service API.

Autenticacion (segun "Device Lock Service API 1.0.3"):
    ts         = timestamp actual en milisegundos (string)
    encryptStr = RequestURL + ts          # ej: /device-lock/api/v1/device/status
    signature  = Base64( HMAC_SHA1(SecretKey, encryptStr) )
    Authorization = AccessKey + ":" + signature + ":" + ts

Solo usa la libreria estandar (no requiere 'pip install').
"""

import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
import urllib.error

# --- Credenciales por entorno (de la tabla de access/secret keys) ---
ENVIRONMENTS = {
    "DEV": {
        "host": "dev-saas.zeasn.tv",
        "access_key": "10f867d3a68fe34c78948eea53cba5ad57",
        "secret_key": "1043db433d509e46d883099a8a6c1b7878",
    },
    "ACC": {
        "host": "acc-saas.zeasn.tv",
        "access_key": "10a7ea42f147464a3eaf2b82c47c901569",
        "secret_key": "10c278fefd9ce34c3c965cf63681abe961",
    },
    "PROD": {
        "host": "saas.zeasn.tv",
        "access_key": "1095d44693c7c147d698c3aab70de90287",
        "secret_key": "12bce1e626af7348829dd242bf1d7f4bca",
    },
}

API_BASE = "/device-lock/api/v1"


def build_authorization(request_url: str, access_key: str, secret_key: str) -> str:
    """Genera el valor del header Authorization."""
    ts = str(int(time.time() * 1000))
    encrypt_str = request_url + ts
    digest = hmac.new(
        secret_key.encode("utf-8"),
        encrypt_str.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    signature = base64.b64encode(digest).decode("utf-8")
    return f"{access_key}:{signature}:{ts}"


def call_api(env_name: str, api_path: str, params: dict | None = None) -> dict:
    """Hace un GET autenticado a la API y devuelve el JSON parseado."""
    env = ENVIRONMENTS[env_name]
    request_url = f"{API_BASE}{api_path}"  # ruta usada para firmar (sin host ni query)

    full_url = f"https://{env['host']}{request_url}"
    if params:
        full_url += "?" + urllib.parse.urlencode(params)

    authorization = build_authorization(
        request_url, env["access_key"], env["secret_key"]
    )

    req = urllib.request.Request(full_url, method="GET")
    req.add_header("Authorization", authorization)
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
        return {"http_status": resp.status, "body": json.loads(body)}


def main():
    # PROD es el entorno donde las credenciales actuales estan provisionadas.
    # (DEV/ACC devuelven 401 "USERINFO IS NULL" porque la llave no esta dada de alta alli.)
    env_name = "PROD"
    env = ENVIRONMENTS[env_name]

    print(f"Conectando a WhaleTV Device Lock API  [{env_name}]")
    print(f"Host: https://{env['host']}{API_BASE}")
    print("-" * 55)

    # Endpoint de prueba: estado de un dispositivo.
    # Aunque el dispositivo no exista, una respuesta JSON valida confirma
    # que la conexion y la autenticacion (firma HMAC) funcionan.
    try:
        result = call_api(env_name, "/device/status", {"eui64": "0000000000000000"})
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        if e.code == 401:
            print("[FALLO] HTTP 401 - Autenticacion rechazada.")
            print("        Revisa access/secret key o el reloj del sistema.")
        else:
            print(f"[FALLO] HTTP {e.code} - {e.reason}")
        print(f"        Respuesta: {detail}")
        return
    except urllib.error.URLError as e:
        print(f"[FALLO] No se pudo establecer conexion: {e.reason}")
        return

    data = result["body"]
    error_code = str(data.get("errorCode"))

    if error_code == "0":
        print("CONEXION EXITOSA - Autenticacion valida y dispositivo encontrado.")
    elif error_code == "260001":
        # La firma fue aceptada; solo el dispositivo de prueba no existe.
        print("CONEXION EXITOSA - Autenticacion valida (errorCode 260001: device de prueba no existe).")
    else:
        print(f"CONEXION EXITOSA - Respuesta recibida (errorCode={error_code}: {data.get('errorMsg')}).")

    print("-" * 55)
    print(f"HTTP status : {result['http_status']}")
    print("Respuesta JSON del servidor:")
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
