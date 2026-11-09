// Utilities shared by the interface modules

function round(f) {
    return Math.round(f * 100) / 100.;
}

function formatTimer(timer) {
    let negative = '';
    timer = Math.round(timer || 0);
    if (timer < 0) {
        negative = '-';
        timer *= -1;
    }

    let seconds = String(timer % 60);
    let minutes = String(Math.floor(timer / 60));

    return negative + minutes.padStart(2, '0') + ':' + seconds.padStart(2, '0');
}

// Escapes a text to be inserted in HTML
function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function capitalize(text) {
    text = String(text ?? '');
    return text.charAt(0).toUpperCase() + text.slice(1);
}

// "green1" => ["green", 1]
function robotTeamNumber(robot) {
    let match = /^([a-z]+)(\d+)$/.exec(robot);
    return match ? [match[1], parseInt(match[2])] : [robot, null];
}

// Shows a notification (toast) in the corner of the screen
function notify(message, type = 'danger', delay = 5000) {
    let icons = {
        danger: 'bi-exclamation-octagon-fill',
        warning: 'bi-exclamation-triangle-fill',
        success: 'bi-check-circle-fill',
        info: 'bi-info-circle-fill',
    };
    let toast = $(
        '<div class="toast align-items-center text-bg-' + type + ' border-0" role="alert" aria-live="assertive" aria-atomic="true">'
        + '<div class="d-flex"><div class="toast-body">'
        + '<i class="bi ' + (icons[type] || icons.info) + '"></i>&nbsp;' + escapeHtml(message)
        + '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>'
        + '</div>'
    );
    $('#notifications').append(toast);
    let bsToast = new bootstrap.Toast(toast[0], { delay: delay });
    toast.on('hidden.bs.toast', function () { toast.remove(); });
    bsToast.show();
}

// Asks a confirmation (in a modal dialog) before doing something
function confirmDialog(message, onConfirm, confirmLabel = 'Confirm') {
    let modal = $(
        '<div class="modal fade" tabindex="-1" aria-hidden="true"><div class="modal-dialog modal-dialog-centered"><div class="modal-content">'
        + '<div class="modal-body">' + escapeHtml(message) + '</div>'
        + '<div class="modal-footer">'
        + '<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>'
        + '<button type="button" class="btn btn-danger confirm-button">' + escapeHtml(confirmLabel) + '</button>'
        + '</div></div></div></div>'
    );
    $('body').append(modal);
    let bsModal = new bootstrap.Modal(modal[0]);
    modal.find('.confirm-button').click(function () {
        bsModal.hide();
        onConfirm();
    });
    modal.on('hidden.bs.modal', function () { modal.remove(); });
    bsModal.show();
}
