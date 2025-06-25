# Fichero: chatproxy/__init__.py - Versión Final de Producción

import os
import json
import logging
import requests
from datetime import datetime, timedelta, timezone

import azure.functions as func
from azure.data.tables import TableClient, UpdateMode
from azure.core.exceptions import ResourceNotFoundError, ResourceModifiedError

# --- 1. Configuración ---
# Estas variables se obtienen de la Configuración de la Aplicación,
# que a su vez las obtiene de forma segura desde Key Vault.
ENDPOINT_URL = os.getenv("ENDPOINT_URL")
OPENAI_KEY   = os.getenv("AZURE_OPENAI_API_KEY")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")
HEADERS      = {"api-key": OPENAI_KEY, "Content-Type": "application/json"}

# Se usa la nueva cadena de conexión segura y restringida, obtenida desde Key Vault.
STORAGE_CONN_STR = os.getenv("QUOTA_TABLE_CONN_STR")

# El cliente se inicializa una sola vez para reutilizar la conexión.
# El nombre de la tabla ('quota') está incluido en la SAS, por lo que no se especifica aquí.
table_client = TableClient.from_connection_string(conn_str=STORAGE_CONN_STR, table_name="quota")
if not STORAGE_CONN_STR:
    logging.warning("🔴 QUOTA_TABLE_CONN_STR está vacía")
else:
    logging.warning("🟡 QUOTA_TABLE_CONN_STR len=%d, primeras 60 chars=%s…",
                    len(STORAGE_CONN_STR), STORAGE_CONN_STR[:60])

# --- 2. Lógica de Cuota Atómica y Robusta ---

def check_and_increment_quota(user_id: str) -> int:
    """
    Verifica y actualiza la cuota del usuario de forma atómica usando ETags.
    Devuelve el número de usos restantes, o -1 si la cuota se ha excedido.
    """
    PARTITION_KEY = "quota"
    ROW_KEY = user_id
    QUOTA_LIMIT = 600
    
    # Bucle de reintento para manejar colisiones de concurrencia
    for _ in range(3):
        try:
            try:
                # Intenta obtener la entidad (el contador) del usuario
                entity = table_client.get_entity(PARTITION_KEY, ROW_KEY)
                entity_etag = entity.metadata["etag"]
            except ResourceNotFoundError:
                # Si el usuario no existe, se crea su primera entrada
                entity = {
                    "PartitionKey": PARTITION_KEY, 
                    "RowKey": ROW_KEY, 
                    "counter": 0, 
                    "reset_date": datetime.now(timezone.utc).isoformat()
                }
                entity_etag = None # No hay ETag para una entidad nueva

            # Comprueba si ha pasado más de 30 días para reiniciar el contador
            reset_date = datetime.fromisoformat(entity["reset_date"])
            if (datetime.now(timezone.utc) - reset_date) > timedelta(days=30):
                entity["counter"] = 0
                entity["reset_date"] = datetime.now(timezone.utc).isoformat()

            # Si la cuota ya se ha excedido, no incrementa y devuelve -1
            if entity["counter"] >= QUOTA_LIMIT:
                return -1

            # Incrementa el contador
            entity["counter"] += 1

            # Intento de escritura atómica:
            # Si 'entity_etag' es None, se crea la entidad (create_entity)
            # Si 'entity_etag' existe, se actualiza (update_entity) con el ETag para asegurar atomicidad
            if not entity_etag:
                table_client.create_entity(entity=entity)
            else:
                # LÍNEA 80 CORREGIDA
                table_client.update_entity(entity, mode=UpdateMode.REPLACE, etag=entity_etag)
            
            # Éxito: devuelve el número de usos restantes
            return QUOTA_LIMIT - entity["counter"]

        except ResourceModifiedError:
            # Ocurrió una colisión (otra petición actualizó la entidad mientras tanto).
            # El bucle 'for' hará que lo reintentemos.
            logging.warning(f"Conflicto de concurrencia para el usuario {user_id}. Reintentando...")
            continue
    
    # Si se falla después de 3 reintentos, se deniega la petición por seguridad.
    logging.error(f"No se pudo actualizar la cuota para el usuario {user_id} después de 3 reintentos.")
    return -1

# --- 3. Función Principal ---

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Obtener el user_id de la cabecera, que ha sido validada por APIM
        user_id = req.headers.get('X-User-Id')
        if not user_id:
            return func.HttpResponse("Falta la cabecera X-User-Id.", status_code=400)

        # --- Verificación de cuota (se hace ANTES de llamar a OpenAI) ---
        remaining = check_and_increment_quota(user_id)
        if remaining < 0:
            return func.HttpResponse(
                json.dumps({"error": "Quota exhausted", "reply": "Límite mensual de uso alcanzado."}),
                status_code=429, # 429 Too Many Requests
                mimetype="application/json"
            )

        # --- Lógica de IA (solo se ejecuta si hay cuota) ---
        req_body = req.get_json()
        message = req_body.get('message')
        vs_id = req_body.get('vs_id')

        # (Aquí iría tu lógica para construir 'msgs' y buscar en el Vector Store si es necesario)
        msgs=[{"role":"system","content":"Eres LAIER, asistente legal experto en derecho español."}]
        if vs_id:
            # Aquí la lógica para llamar a search_ctx(vs_id, message)
            pass
        msgs.append({"role":"user","content":message})
        
        response = requests.post(
            f"{ENDPOINT_URL}/openai/deployments/{DEPLOYMENT_NAME}/chat/completions?api-version=2024-02-01",
            headers=HEADERS,
            json={"messages": msgs, "max_tokens": 800},
            timeout=90 # Timeout para la llamada a OpenAI
        )
        response.raise_for_status() # Lanza error si la llamada a OpenAI falla (ej. 5xx)
        ans = response.json()["choices"][0]["message"]["content"]
        
        # --- Respuesta Exitosa ---
        # Se añade el contador de usos restantes a la respuesta para el frontend
        response_body = {
            "reply": ans,
            "vs_id": vs_id,
            "remaining_quota": remaining
        }
        
        return func.HttpResponse(
            json.dumps(response_body),
            mimetype="application/json",
            status_code=200
        )

    except requests.exceptions.HTTPError as e:
        # Aunque la llamada a OpenAI falle, el usuario ya ha gastado una llamada de su cuota.
        # Es importante registrar este error para monitorización.
        logging.error(f"Error en la llamada a OpenAI: {e}")
        return func.HttpResponse("Error al comunicarse con el servicio de IA.", status_code=502) # 502 Bad Gateway

    except Exception as e:
        logging.exception("chatproxy ha fallado de forma inesperada.")
        return func.HttpResponse("Ha ocurrido un error interno.", status_code=500)
