const API = "/api";
let vs_id = null;
const chatLog = document.getElementById('chat-log');
const msgInput = document.getElementById('msg-input');
const fileInput = document.getElementById('file-input');

// Enviar mensaje con la tecla Enter
msgInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
    }
});

// Función para añadir una burbuja de chat al log
function addBubble(message, sender) {
    const bubble = document.createElement('div');
    bubble.classList.add('message-bubble');
    bubble.classList.add(sender === 'user' ? 'user-bubble' : 'ai-bubble');
    bubble.textContent = message;
    chatLog.appendChild(bubble);
    // Auto-scroll hacia abajo
    chatLog.scrollTop = chatLog.scrollHeight;
}

async function maybeUpload() {
    const f = fileInput.files[0];
    if (!f) return;
    addBubble(`Subiendo fichero: ${f.name}`, 'ai-bubble');
    const fd = new FormData();
    fd.append("file", f);
    if (vs_id) fd.append("vs_id", vs_id);
    const j = await fetch(API + "/upload", { method: "POST", body: fd }).then(r => r.json());
    vs_id = j.vs_id;
    addBubble(`Fichero subido con éxito. ID de Vector Store: ${vs_id}`, 'ai-bubble');
    fileInput.value = ""; // Limpiar el input de fichero
}

async function send() {
    await maybeUpload();
    const txt = msgInput.value.trim();
    if (!txt) return;

    addBubble(txt, 'user');
    msgInput.value = ""; // Limpiar el input de texto

    // Mostrar un mensaje de "pensando..."
    addBubble("...", 'ai-bubble');

    try {
        const response = await fetch(API + "/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: txt, vs_id })
        });

        // Eliminar el mensaje de "pensando..."
        chatLog.removeChild(chatLog.lastChild);

        if (!response.ok) {
             addBubble(`Error: ${response.statusText}`, 'ai-bubble');
             return;
        }

        const j = await response.json();
        addBubble(j.reply, 'ai-bubble');

    } catch (error) {
        // Eliminar el mensaje de "pensando..."
        chatLog.removeChild(chatLog.lastChild);
        addBubble(`Ha ocurrido un error de red: ${error.message}`, 'ai-bubble');
    }
}
