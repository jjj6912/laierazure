# ─── upload_file/__init__.py – versión de producción (JSON + Base64) ─────────
import os, uuid, json, base64, requests, logging
import azure.functions as func

# 1 ▸ Configuración (variables apuntan a Key Vault)
ENDPOINT_URL  = os.getenv("ENDPOINT_URL")            # https://<aoai>.openai.azure.com
OPENAI_KEY    = os.getenv("AZURE_OPENAI_API_KEY")
HEADERS       = {"api-key": OPENAI_KEY}
API_VERSION   = "2024-05-01-preview"

# Límite y tipos permitidos
MAX_UPLOAD = 4 * 1024 * 1024   # 4 MiB (coherente con frontend)
ALLOWED_CT = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword"
}

# 2 ▸ Helpers
def make_vector_store() -> str:
    name = f"vs-{uuid.uuid4().hex[:8]}"
    r = requests.post(
        f"{ENDPOINT_URL}/openai/vectorstores?api-version={API_VERSION}",
        headers=HEADERS, json={"name": name}, timeout=30)
    r.raise_for_status()
    return r.json()["id"]

def error(msg: str, code: int = 400):
    return func.HttpResponse(msg, status_code=code)

# 3 ▸ Function principal
def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body       = req.get_json()
        data_url   = body.get("file_data_url")
        file_name  = body.get("file_name", "uploaded_file")
        vs_id      = body.get("vs_id") or make_vector_store()

        if not data_url:
            return error("Falta 'file_data_url' en la petición.", 400)

        try:
            header, encoded = data_url.split(",", 1)
        except ValueError:
            return error("Formato de data-URL no válido.", 400)

        if len(encoded) > MAX_UPLOAD:
            return error("Fichero demasiado grande.", 413)

        file_bytes   = base64.b64decode(encoded, validate=True)
        content_type = header.partition(":")[2].partition(";")[0]

        if content_type not in ALLOWED_CT:
            return error("Tipo de fichero no permitido.", 415)

        # 3.1 Subir a Azure OpenAI Files
        files = {"file": (file_name, file_bytes, content_type)}
        up = requests.post(
            f"{ENDPOINT_URL}/openai/files?api-version={API_VERSION}&purpose=assistants",
            headers=HEADERS, files=files, timeout=60)
        up.raise_for_status()
        file_id = up.json()["id"]

        # 3.2 Asociar al Vector Store
        batch = requests.post(
            f"{ENDPOINT_URL}/openai/vectorstores/{vs_id}/file_batches?api-version={API_VERSION}",
            headers=HEADERS, json={"file_ids": [file_id]}, timeout=30)
        batch.raise_for_status()

        logging.info("File %s linked to vector store %s", file_id, vs_id)

        return func.HttpResponse(
            json.dumps({"vs_id": vs_id, "file_id": file_id}),
            mimetype="application/json", status_code=200)

    except Exception:
        logging.exception("upload_file failed")
        return error("Ha ocurrido un error interno.", 500)


