(function(){
    function handleDismiss(e){
        var btn = e.currentTarget;
        var ticker = btn.getAttribute('data-ticker');
        if(!ticker) return;
        var card = document.getElementById('stock-' + ticker);
        if(card){
            card.style.transition = 'opacity 0.18s ease';
            card.style.opacity = '0.2';
        }

        fetch('/api/pending/seen', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker: ticker })
        }).then(function(resp){
            if(!resp.ok) throw new Error('Network response not ok');
            if(card) card.remove();
        }).catch(function(err){
            if(card){ card.style.opacity = '1'; }
            console.error('Failed to mark pending seen:', err);
        });
    }

    document.addEventListener('DOMContentLoaded', function(){
        var buttons = document.querySelectorAll('.dismiss-rejected');
        buttons.forEach(function(b){ b.addEventListener('click', handleDismiss); });
    });
})();
