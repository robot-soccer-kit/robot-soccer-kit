function referee_initialize(backend)
{
    let displayed_toast_nb = 0 ;

    let event_neutral_tpl = '';
    $.get('/static/referee_event_neutral.html', function(data) {
        event_neutral_tpl = data;
    });
    let event_team_tpl = ''
    $.get('/static/referee_event_team.html', function(data) {
        event_team_tpl = data;
    });

    setInterval(function() {
        backend.getScore("blue", function(score) {
            $( "#BlueScore" ).html(score);
        });

        backend.getScore("green", function(score) {
            $( "#GreenScore" ).html(score);
        });

        backend.getPenalty(function(penalties) {
            for (let robot in penalties) {
                let [remaining, max] = penalties[robot];
                let div = $('.robot-penalty[rel='+robot+'] .progress-bar');
                if (remaining !== null) {
                    let pct = remaining * 100. / max;
                    div.attr("style","width:"+pct+"%");
                    div.html("<b>"+remaining+" / "+max+" s<b>");
                } else {
                    div.attr("style","width:0%");
                    div.text('')
                }
            }
        });

        backend.getTimer(function(time) {
            $('.TimerMinutes').html(formatTimer(time))
            
            if (time < 0) {
                $(".TimerMinutes").addClass('text-danger');
            } else {
                $(".TimerMinutes").removeClass('text-danger');
            }
        });

        backend.getGameState(function(game_state) {
            $(".GameState").html(game_state);
        });

        backend.getRefereeHistory(3, function(history) {
            for (let history_entry of history) {
                [num, time, team, referee_event] = history_entry
                    $("#NoHistory").html('')

                    if (num >= displayed_toast_nb) {
                        let html = '';

                        let vars = {
                            'id': displayed_toast_nb,
                            'team': team,
                            'title': referee_event,
                            'timestamp': formatTimer(time),
                            'event': referee_event
                        };

                        if (team === 'neutral'){
                            html = event_neutral_tpl
                        } else {
                            html = event_team_tpl
                        }

                        for (let key in vars) {
                            html = html.replaceAll('{'+key+'}', vars[key])
                        }

                        $("#RefereeHistory").append(html);
                        $('#toast-'+displayed_toast_nb).toast('show');
                        $("#tchat").scrollTop($("#tchat")[0].scrollHeight);

                        displayed_toast_nb = displayed_toast_nb+1;

                    }
            }
        });

    }, 200);

    $('.toast').toast('show');

    // Game Start&Stop
    $('.start-game').click(function() {
        backend.startGame();
        $('.start-game').addClass('d-none');
        $('.pause-game-grp').removeClass('d-none');   

        displayed_toast_nb = 0;
        $("#RefereeHistory").html('');
        $("#NoHistory").html('<h6 class="text-muted">No History</h6>');
        $("#MidTimeChange").prop("disabled", false);

        $('.robot-penalty').each(function() {
            $(this).find('.unpenalize').prop("disabled", false);
            $(this).find('.penalize').prop("disabled", false);
        });
    });

    $('.pause-game').click(function() {
        backend.pauseGame();
        $('.resume-game-grp').removeClass('d-none');
        $('.pause-game-grp').addClass('d-none');
    });

    $('.resume-game').click(function() {
        backend.resumeGame();
        $('.pause-game-grp').removeClass('d-none');
        $('.resume-game-grp').addClass('d-none');
    });

    $('.stop-game').click(function() {
        backend.stopGame();
        $('.start-game').removeClass('d-none');
        $('.pause-game-grp').addClass('d-none');
        $('.resume-game-grp').addClass('d-none');
        $("#MidTimeChange").prop("disabled", true);

        $('.robot-penalty').each(function() {
            $(this).find('.unpenalize').prop("disabled", true);
            $(this).find('.penalize').prop("disabled", true);
        });
    });

    
    // Half Time
    $('#MidTimeChange').click(function() {
        backend.MidTimeChangeColorField();
        backend.setTeamSides();
        if ($('.robot-penalize-tab').css("flex-direction") === "row-reverse"){
            $('.robot-penalize-tab').css("flex-direction", "row");
        }
        else{
            $('.robot-penalize-tab').css("flex-direction", "row-reverse");
        }

        $("#RefereeHistory").append('<h5 class="text-muted m-3">Half Time</h5>');
        backend.startHalfTime();
    });

    $('#Y_ChangeCover').click(function() {
        $('.ChangeCover').addClass('d-none');
        $('.MidTimeIdentify').removeClass('d-none');
        $('.MidTimeIdentifyBefore').removeClass('d-none');
    });

    $('#N_ChangeCover').click(function() {
        $('.ChangeCover').addClass('d-none');
        $('.SecondHalfTime').removeClass('d-none');
    });

    $('#BtnMidTimeIdentify').click(function() {
        $('.MidTimeIdentifyBefore').addClass('d-none');
        $('.MidTimeIdentifyWait').removeClass('d-none');
        setTimeout(function() {
            $('.MidTimeIdentifyWait').addClass('d-none');
            $('#Next_MidTimeIdentify').removeClass('d-none');
            $('.MidTimeIdentifyDone').removeClass('d-none');
            $('.MidTimeIdentifyDone').removeClass('d-none');
            $('.MidTimeIdentifyWait').addClass('d-none');
            }, 4000);
    });

    $('#Next_MidTimeIdentify').click(function() {
        $('#Next_MidTimeIdentify').addClass('d-none');
        $('.MidTimeIdentifyDone').addClass('d-none');
        $('.MidTimeIdentify').addClass('d-none');
        $('.MidTimeIdentifyBefore').addClass('d-none');
        $('.SecondHalfTime').removeClass('d-none');
    });

    $('#BtnSecondHalfTime').click(function() {
        setTimeout(function() {
        $('.ChangeCover').removeClass('d-none');
        $('.MidTimeIdentify').addClass('d-none');
        $('.SecondHalfTime').addClass('d-none');
        }, 500);
        backend.startSecondHalfTime();
    });

    // Teams Names
    $( ".team-name" ).change(function() {
        backend.setTeamNames($(this).attr('rel'),$(this).val())
    });

    // Scores 
    $('.score-zone').each(function() {
        let robot_id = $(this).attr('rel');

        $(this).find('.up-score').click(function() {
            backend.updateScore(robot_id, 1);
        });

        $(this).find('.down-score').click(function() {
            backend.updateScore(robot_id, -1);
        });
    });


    $('.reset-score').click(function() {
        backend.resetScore();
    });


    // Place Robots
    $('#Strd-place').click(function() {
        backend.placeGame();
    });
    

    // Robots Penalties
    $('.robot-penalty').each(function() {
        let robot_id = $(this).attr('rel');

        $(this).find('.penalize').click(function() {
            backend.addPenalty(5, robot_id);
            console.log(robot_id)
        });
        $(this).find('.unpenalize').click(function() {
            backend.cancelPenalty(robot_id);
            console.log(robot_id)
        });
    });
}