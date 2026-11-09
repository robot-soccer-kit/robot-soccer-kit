// Competition mode: teams (name and key) saved in the browser, to set them quickly for a game

function competition_initialize(backend) {
    let teams = {};

    try {
        teams = JSON.parse(localStorage.getItem('teams')) || {};
    } catch (e) {
        teams = {};
    }

    function save() {
        try {
            localStorage.setItem('teams', JSON.stringify(teams));
        } catch (e) { }
    }

    function setTeam(name, color) {
        $('.team-name[rel="' + color + '"]').val(name).change();
        $('.key-' + color).val(teams[name]).change();
        notify(name + ' plays as ' + color, 'success', 3000);
    }

    function renderTeams() {
        let html = '';
        for (let name of Object.keys(teams).sort()) {
            html += '<tr data-team="' + escapeHtml(name) + '">'
                + '<td class="ps-3 fw-semibold">' + escapeHtml(name) + '</td>'
                + '<td class="text-end pe-3">'
                + '<span class="team-green"><button class="btn btn-sm btn-team me-1 play-as" data-color="green" type="button">Green</button></span>'
                + '<span class="team-blue"><button class="btn btn-sm btn-team me-3 play-as" data-color="blue" type="button">Blue</button></span>'
                + '<button class="btn btn-sm btn-outline-danger team-remove" type="button" title="Remove"><i class="bi bi-trash"></i></button>'
                + '</td>'
                + '</tr>';
        }
        if (!html) {
            html = '<tr><td colspan="2" class="text-center text-body-secondary py-4">No team yet</td></tr>';
        }
        $('.competition-teams').html(html);
    }

    $('.competition-teams').on('click', '.play-as', function () {
        setTeam($(this).closest('tr').attr('data-team'), $(this).data('color'));
    });
    $('.competition-teams').on('click', '.team-remove', function () {
        let name = $(this).closest('tr').attr('data-team');
        confirmDialog('Remove the team "' + name + '"?', function () {
            delete teams[name];
            save();
            renderTeams();
        }, 'Remove');
    });

    $('.add-team-form').submit(function (event) {
        event.preventDefault();
        let name = $('.add-team-name').val().trim();
        if (!name) {
            return;
        }
        teams[name] = $('.add-team-password').val();
        save();
        renderTeams();
        $('.add-team-name, .add-team-password').val('');
    });

    renderTeams();
}
