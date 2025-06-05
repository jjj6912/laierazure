import azure.functions as func
import os
import mimetypes

def main(req: func.HttpRequest) -> func.HttpResponse:
    filepath = req.route_params.get("filepath")
    if not filepath:
        return func.HttpResponse("File path not provided", status_code=400)

    full_path = os.path.join(os.path.dirname(__file__), "../wwwroot", filepath)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        with open(full_path, "rb") as f:
            content = f.read()
        mime_type, _ = mimetypes.guess_type(full_path)
        return func.HttpResponse(content, mimetype=mime_type or "application/octet-stream")
    else:
        return func.HttpResponse("File not found", status_code=404)
