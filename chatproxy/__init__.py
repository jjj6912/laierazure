# Fichero: chatproxy/__init__.py - Versión Final con Cuota Atómica

import os
import json
import logging
import requests
from datetime import datetime, timedelta, timezone

import azure.functions as func
from azure.data.tables import TableClient, UpdateMode
from azure.core.exceptions import ResourceNotFoundError

# --- 1. Configuración ---
ENDPOINT_URL = os.getenv("ENDPOINT_URL")
OPENAI_KEY   = os.getenv("AZURE_OPENAI_API_KEY")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")
HEADERS      = {"api-key": OPENAI_KEY, "Content-Type": "application/json"}
STORAGE_CONN_STR = os.getenv("AzureWebJobsStorage")

# Inicializa el cliente para Azure Table Storage
table_client = TableClient.from_connection_string(STORAGE_CONN_STR, table_name="quota")

# --- 2. Lógica de Cuota Atómica ---

def check_and_increment_quota(user_id: str) -> int:
    """
    Verifica y actualiza la cuota del usuario de forma atómica.
    Devuelve el número de usos restantes, o -1 si la cuota se ha excedido.
    """
    PARTITION_KEY = "quota"
    ROW_KEY = user_id
    QUOTA_LIMIT = 600

    try:
        # Intenta obtener la entidad (el contador) del usuario
        entity = table_client.get_entity(PARTITION_KEY, ROW_KEY)
    except ResourceNotFoundError:
        # Si el usuario no existe, se crea su primera entrada
        entity = {
            "PartitionKey": PARTITION_KEY, 
            "RowKey": ROW_KEY, 
            "counter": 1, 
            "reset_date": datetime.now(timezone.utc).isoformat()
        }
        table_client.create_entity(entity=entity)
        return QUOTA_LIMIT - 1

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

    # Actualiza la entidad en la tabla. El modo "Replace" con un ETag
    # asegura que la operación es atómica y evita "race conditions".
    table_client.update_entity(entity, mode=UpdateMode.REPLACE)
    
    return QUOTA_LIMIT - entity["counter"]

# --- 3. Función Principal ---

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Obtiene el user_id de la cabecera, que ha sido validado por APIM
        user_id = req.headers.get('X-User-Id')
        if not user_id:
            return func.HttpResponse("Falta la cabecera X-User-Id.", status_code=400)

        # --- Verificación de cuota ---
        remaining = check_and_increment_quota(user_id)
        if remaining < 0:
            return func.HttpResponse(
                json.dumps({"error": "Quota exhausted.", "reply": "Límite mensual alcanzado."}),
                status_code=429, # 429 Too Many Requests
                mimetype="application/json"
            )

        # --- Lógica de IA (solo se ejecuta si hay cuota) ---
        req_body = req.get_json()
        message = req_body.get('message')
        vs_id = req_body.get('vs_id')

        # (Aquí va tu lógica para construir 'msgs' y llamar a OpenAI)
        # ...
        # Por ejemplo:
        msgs=[{"role":"system","content":"Eres LAIER, asistente legal experto en derecho español."}]
        # if vs_id: ...
        msgs.append({"role":"user","content":message})
        
        response = requests.post(
            f"{ENDPOINT_URL}/openai/deployments/{DEPLOYMENT_NAME}/chat/completions?api-version=2024-02-01",
            headers=HEADERS,
            json={"messages": msgs, "max_tokens": 800}
        )
        response.raise_for_status()
        ans = response.json()["choices"][0]["message"]["content"]
        
        # --- Respuesta Exitosa ---
        # Se añade el contador de usos restantes a la respuesta
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

    except Exception as e:
        logging.exception("chatproxy ha fallado")
        return func.HttpResponse(f"Ha ocurrido un error interno: {str(e)}", status_code=500)

