import os, json, uuid, logging
import azure.functions as func
from openai import AzureOpenAI

# La versión de la API para asistentes
API_VERSION = "2024-05-01-preview"

def get_settings():
    ep  = os.getenv("AZURE_OPENAI_ENDPOINT")
    key = os.getenv("AZURE_OPENAI_KEY")
    if not ep or not key:
        logging.error("Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_KEY")
        return None
    return ep, key

def main(req: func.HttpRequest) -> func.HttpResponse:
    settings = get_settings()
    if not settings:
        return func.HttpResponse("Server configuration error", status_code=500)
    EP, KEY = settings

    try:
        client = AzureOpenAI(api_version=API_VERSION, azure_endpoint=EP, api_key=KEY)

        file      = req.files.get("file")
        thread_id = req.form.get("thread_id", "")
        vs_id     = req.form.get("vs_id", "")

        if not file:
            return func.HttpResponse("No file", status_code=400)

        # 1. si aún no hay vector store para este hilo, créalo
        if not vs_id:
            vector_store = client.beta.vector_stores.create(name=f"vs-{uuid.uuid4().hex[:8]}")
            vs_id = vector_store.id

        # 2. sube el archivo a OpenAI
        file_bytes = file.stream.read()
        file_obj = client.files.create(file=(file.filename, file_bytes), purpose='assistants')
        
        # 3. indexa el fichero en el vector store
        client.beta.vector_stores.file_batches.create(
            vector_store_id=vs_id,
            file_ids=[file_obj.id]
        )

        return func.HttpResponse(
            json.dumps({"file_id": file_obj.id, "vs_id": vs_id, "thread_id": thread_id}),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error(f"Error in upload_file: {e}")
        return func.HttpResponse("Internal Server Error", status_code=500)
    return func.HttpResponse(
        json.dumps({"file_id": fid, "vs_id": vs_id, "thread_id": thread_id}),
        mimetype="application/json",
    )
