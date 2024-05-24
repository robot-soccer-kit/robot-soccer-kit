function control_initialize(backend) {
    $.get('static/team.html', function(team_template) {

        for (let team of ['green', 'blue']) {
            $('.teams').append(team_template.replace(/{team}/g, team));

            $('.allow-'+team).change(function() {
                backend.allow_team_control(team, $(this).is(':checked'));
            });

            $('.key-'+team).change(function() {
                backend.set_key(team, $(this).val());
            });

            // $('.key-'+team).focus(function() {
            //     $(this).attr('type', 'text');
            // });
            // $('.key-'+team).blur(function() {
            //     $(this).attr('type', 'password');
            // });
        }

        $('.emergency').click(function() {
            backend.emergency();
        });

        setInterval(function() {
            backend.control_status(function(game) {
                for (let team of ['green', 'blue']) {
                    $('.allow-'+team).prop('checked', game[team]['allow_control']);
                    $('.packets-'+team).text(game[team]['packets']+' packets');
                    if (!$('.key-'+team).is(':focus')) {
                        $('.key-'+team).val(game[team]['key']);
                    }
                }
                if(game['green']['allow_control'] && game['blue']['allow_control'])
                {
                    $('body').removeClass('control-warning');
                }else {
                    $('body').addClass('control-warning');
                }
            });
        }, 200);
    });
}