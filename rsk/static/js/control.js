function capitalize_first_letter(string){
    const strUp = string.charAt(0).toUpperCase() + string.slice(1);
    return strUp
}
function control_initialize(backend) {
    $.get('static/team.html', function(team_template) {

        for (let team of ['green', 'blue']) {
            $('.teams').append(team_template.replace(/{team}/g, team));

            $('.allow-'+team).change(function() {
                backend.allowTeamControl(team, $(this).is(':checked'));
            });

            $('.key-'+team).change(function() {
                backend.setKey(team, $(this).val());
            });

            $('.key-'+team).focus(function() {
                $(this).attr('type', 'text');
            });
            $('.key-'+team).blur(function() {
                $(this).attr('type', 'password');
            });
        }

        $('.emergency').click(function() {
            backend.emergency();
        });

        setInterval(function() {
            backend.getGame(function(game) {
                for (let team of ['green', 'blue']) {
                    $('.allow-'+team).prop('checked', game[team]['allow_control']);
                    $('.packets-'+team).text(game[team]['packets']+' packets');
                    if (!$('.key-'+team).is(':focus')) {
                        $('.key-'+team).val(game[team]['key']);
                    }
                }
            });
        }, 200);
    });
}