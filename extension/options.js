const ids = ['username','password','targetUrl','autoLogin','autoNav','autoClick','delayMin','delayMax','pollMs','maxPasses','maxRetry','retryWaitMs'];

async function load(){
  const d = await chrome.storage.sync.get(ids);
  ids.forEach(k=>{
    const el = document.getElementById(k);
    if (el.type === 'checkbox') el.checked = d[k] !== undefined ? d[k] : el.checked;
    else el.value = d[k] !== undefined ? d[k] : el.value;
  });
}
async function save(){
  const obj = {};
  ids.forEach(k=>{
    const el = document.getElementById(k);
    obj[k] = el.type === 'checkbox' ? el.checked
           : el.type === 'number'  ? parseInt(el.value,10)
           : el.value;
  });
  await chrome.storage.sync.set(obj);
  document.getElementById('saved').style.display = 'block';
  setTimeout(()=>document.getElementById('saved').style.display='none', 2500);
}
document.getElementById('save').addEventListener('click', save);
load();
