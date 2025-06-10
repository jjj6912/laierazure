const API = "/api";           // proxy sin clave
let thread=null, vs_id=null;

async function maybeUpload(){
  const f = document.getElementById('fileInp').files[0];
  if(!f) return;
  const fd = new FormData();
  fd.append("file", f);
  if(vs_id) fd.append("vs_id", vs_id);
  const j = await fetch(API+"/upload",{method:"POST",body:fd}).then(r=>r.json());
  vs_id = j.vs_id;
  document.getElementById('fileInp').value="";
}

async function send(){
  await maybeUpload();
  const txt=document.getElementById('msg').value.trim();
  if(!txt) return;
  document.getElementById('log').textContent+="👤 "+txt+"\n";
  const j = await fetch(API+"/chat",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({message:txt,vs_id})
  }).then(r=>r.json());
  document.getElementById('log').textContent+="🤖 "+j.reply+"\n\n";
  document.getElementById('msg').value="";
  document.getElementById('log').scrollTop=1e9;
}
