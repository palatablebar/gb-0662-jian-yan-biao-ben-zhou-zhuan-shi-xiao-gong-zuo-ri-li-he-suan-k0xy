const input=document.getElementById('table-filter');
input?.addEventListener('input',()=>{const text=input.value.trim();document.querySelectorAll('tbody tr').forEach(row=>row.hidden=!row.textContent.includes(text));});
