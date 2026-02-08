(function(){
    const mainBox = document.getElementById('Main_Box');
    const status = document.getElementById('stock-settings-status');
    const TICKER = mainBox ? mainBox.dataset.ticker : null;

    function showStatus(text, flash=false){
        if(!status) return;
        status.textContent = text;
        if(flash){
            status.classList.add('flash');
            setTimeout(()=> status.classList.remove('flash'), 1200);
        }
    }

    async function postAction(action, payload){
        if(!TICKER){
            console.error('Ticker not set');
            showStatus('Error: missing ticker', true);
            return;
        }
        const url = `/stock/${TICKER}/${action}`;
        try{
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload || {})
            });
            const data = await res.json();
            showStatus(data.message || 'OK', true);
            console.log(action, data);
        } catch(err){
            console.error(err);
            showStatus('Error', true);
        }
    }

    document.getElementById('run-optimiser')?.addEventListener('click', () => {
        postAction('optimiser');
    });

    document.getElementById('run-backtest')?.addEventListener('click', () => {
        postAction('backtest');
    });
})();
