// Control tab: teams allowance and keys, emergency stop

function control_initialize(backend) {
    for (let team of ['green', 'blue']) {
        let card = $(
            '<div class="col-md-6">'
            + '<div class="card team-' + team + ' h-100">'
            + '<div class="card-header d-flex align-items-center gap-2 bg-team">'
            + '<img src="static/markers/' + team + '1.svg" width="28" height="28" alt="" />'
            + '<img src="static/markers/' + team + '2.svg" width="28" height="28" alt="" />'
            + '<span class="ms-1">' + capitalize(team) + ' team</span>'
            + '<span class="ms-auto badge text-bg-light packets-' + team + '"></span>'
            + '</div>'
            + '<div class="card-body">'
            + '<div class="form-check form-switch mb-3">'
            + '<input class="form-check-input allow-' + team + '" type="checkbox" role="switch" id="allow-' + team + '" />'
            + '<label class="form-check-label" for="allow-' + team + '">Allowed to control its robots</label>'
            + '</div>'
            + '<label class="form-label" for="key-' + team + '">Key</label>'
            + '<div class="input-group">'
            + '<span class="input-group-text"><i class="bi bi-key"></i></span>'
            + '<input type="password" class="form-control key-' + team + '" id="key-' + team + '" placeholder="No key: any client can control the robots" autocomplete="off" />'
            + '<button class="btn btn-outline-secondary show-key" type="button" title="Show / hide the key"><i class="bi bi-eye"></i></button>'
            + '</div>'
            + '</div>'
            + '</div>'
            + '</div>'
        );
        $('.teams').append(card);

        card.find('.allow-' + team).change(function () {
            backend.allow_team_control(team, $(this).is(':checked'));
        });
        card.find('.key-' + team).change(function () {
            backend.set_key(team, $(this).val());
        });
        card.find('.show-key').click(function () {
            let input = card.find('.key-' + team);
            let visible = input.attr('type') == 'text';
            input.attr('type', visible ? 'password' : 'text');
            $(this).find('i').toggleClass('bi-eye', visible).toggleClass('bi-eye-slash', !visible);
        });
    }

    $('.emergency').click(function () {
        backend.emergency();
        notify('Emergency stop: all the robots are stopped, and the teams are not allowed to control them anymore', 'warning', 8000);
    });

    setInterval(function () {
        backend.control_status(function (status) {
            let allAllowed = true;
            for (let team of ['green', 'blue']) {
                $('.allow-' + team).prop('checked', status[team].allow_control);
                $('.packets-' + team).text(status[team].packets + ' packets');
                if (!$('.key-' + team).is(':focus')) {
                    $('.key-' + team).val(status[team].key);
                }
                allAllowed = allAllowed && status[team].allow_control;
            }
            $('.control-warning-icon').toggleClass('d-none', allAllowed);
        });
    }, 500);
}
