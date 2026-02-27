document.addEventListener('DOMContentLoaded', function(){
    const form = document.getElementById('add-stock-form');
    if(!form) return;

    const submitBtn = form.querySelector('button[type="submit"]');

    let msgEl = null;
    function clearMessage(){ if(msgEl){ msgEl.remove(); msgEl = null; } }
    function showMessage(text, success){
        clearMessage();
        msgEl = document.createElement('p');
        msgEl.id = success ? 'result_message_success' : 'result_message_failed';
        msgEl.textContent = text;
        form.appendChild(msgEl);
    }

    form.addEventListener('submit', async function(e){
        e.preventDefault();
        clearMessage();
        if(submitBtn) submitBtn.disabled = true;

        const data = { ticker: (form.ticker && form.ticker.value || '').trim() };

        try{
            const res = await fetch('/api/stocks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if(!res.ok){
                let msg = res.statusText;
                try{
                    const body = await res.json();
                    if(body && body.message) msg = body.message;
                } catch(_){
                    try{ msg = await res.text(); } catch(_){}
                }
                showMessage('Failed to add stock: ' + msg, false);
                if(submitBtn) submitBtn.disabled = false;
                return;
            }

            showMessage('Stock created — redirecting...', true);
            setTimeout(()=> window.location.href = '/dashboard', 700);
        }catch(err){
            showMessage('Error: ' + (err && err.message ? err.message : err), false);
            if(submitBtn) submitBtn.disabled = false;
        }
    });
});
