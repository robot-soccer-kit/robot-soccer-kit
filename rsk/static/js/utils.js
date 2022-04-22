
function round(f) {
    return Math.round(f*100)/100.;
}

function formatTimer(timer) {
    let neg = '';
    if (timer < 0) {
        neg = '-'
        timer *= -1;
    }

    seconds = String(timer % 60)
    minutes = String(Math.floor(timer / 60))

    return neg + minutes.padStart(2, '0') + ':' + seconds.padStart(2, '0')
}