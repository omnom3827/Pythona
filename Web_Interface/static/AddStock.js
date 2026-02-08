document.addEventListener('DOMContentLoaded', function(){
    const form = document.getElementById('add-stock-form');
    if(!form) return;

    form.addEventListener('submit', async function(e){
        e.preventDefault();
        const data = {
            ticker: form.ticker.value.trim(),
        };

        try{
            const res = await fetch('/api/stocks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if(!res.ok){
                const txt = await res.text();
                alert('Failed to add stock: ' + (txt || res.statusText));
                return;
            } else {
                window.location.href = '/dashboard';
            }
        }catch(err){
            alert('Error: ' + err);
        }
    });
});
