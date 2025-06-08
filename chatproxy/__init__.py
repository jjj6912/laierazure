import os, json, time, logging
import azure.functions as func
from openai import AzureOpenAI

# La versión de la API para asistentes
API_VERSION = "2024-05-01-preview"

def get_settings():
    ep  = os.getenv("AZURE_OPENAI_ENDPOINT")
    key = os.getenv("AZURE_OPENAI_KEY")
    ag   = os.getenv("AGENT_ID")
    missing = [n for n, v in {
        "AZURE_OPENAI_ENDPOINT": ep,
        "AZURE_OPENAI_KEY": key,
        "AGENT_ID": ag,
    }.items() if not v]
    if missing:
        logging.error(f"Missing environment variables: {', '.join(missing)}")
        return None
    return ep, key, ag

def wait_on_run(client, run, thread_id):
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run

def main(req: func.HttpRequest) -> func.HttpResponse:
    settings = get_settings()
    if not settings:
        return func.HttpResponse("Server configuration error", status_code=500)
    EP, KEY, AG = settings

    try:
        client = AzureOpenAI(api_version=API_VERSION, azure_endpoint=EP, api_key=KEY)

        b        = req.get_json()
        msg      = b.get("message")
        thread_id = b.get("thread_id")
        vs_id    = b.get("vs_id")

        if not msg:
            return func.HttpResponse("Missing message", status_code=400)

        # 1. Si no hay hilo (thread), créalo
        if not thread_id:
            thread = client.beta.threads.create()
            thread_id = thread.id

        # 2. Añade el mensaje del usuario al hilo
        client.beta.threads.messages.create(
            thread_id=thread_id, role="user", content=msg
        )
        
        # 3. Ejecuta el asistente
        tool_resources = {"file_search": {"vector_store_ids": [vs_id]}} if vs_id else {}
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=AG,
            tool_resources=tool_resources
        )
        wait_on_run(client, run, thread_id)

        # 4. Obtén la respuesta
        messages = client.beta.threads.messages.list(thread_id=thread_id, order="asc", after=run.id)
        reply = "No se encontró respuesta."
        for m in messages.data:
             if m.role == 'assistant':
                reply = m.content[0].text.value
                break

        return func.HttpResponse(
            json.dumps({"reply": reply, "thread_id": thread_id, "vs_id": vs_id}),
            mimetype="application/json",
        )
    except Exception as e:
        logging.error(f"Error in chatproxy: {e}")
        return func.HttpResponse("Internal Server Error", status_code=500)
