function capitalize_first_letter(string){
    const strUp = string.charAt(0).toUpperCase() + string.slice(1);
    return strUp
}

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
        backend.getFullGameState(function(game_state) {

            let first_team = game_state["team_colors"][0]
            let second_team = game_state["team_colors"][1]

            // Team names
            if (game_state["team_names"][0] === "" || game_state["team_names"][1] === ""){
                    $(".first-team-name").html(capitalize_first_letter(game_state["team_colors"][0]))
                    $(".second-team-name").html(capitalize_first_letter(game_state["team_colors"][1]))
                }
            else{
                $(".first-team-name").html(game_state["team_names"][0]);
                $(".second-team-name").html(game_state["team_names"][1]);
            }


            // Penalties
            for (let robot in game_state["penalties"]) {
                let [remaining, max] = game_state["penalties"][robot];
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

            // Robots State
            for (let team in game_state["control"]) {
                let team_data = game_state["control"][team]
                for (let number in team_data["preemption_reasons"]) {
                    let reasons = team_data["preemption_reasons"][number]
                    let div = $('.robot-penalty[rel='+team+number+'] .robot-state');
                    
                    if (reasons.length > 0) {
                        let reasons_string = reasons.map(capitalize_first_letter).join(',')
                        div.html('<h6 class="text-danger">'+ reasons_string +'</h6>');

                    } 
                    else if (game_state["game_state_msg"] == "Game is running..."){
                        div.html('<h6>Robot is playing...</h6>');
                    }
                    else {
                        div.html('<h6>Robot is ready to play</h6>');
                    }
                }
            }


            // Scores
            $("#BlueScore").html(game_state["score"][second_team]);
            $("#GreenScore").html(game_state["score"][first_team]);

            
            // Timer
            $('.TimerMinutes').html(formatTimer(game_state["timer"]))
            
            if (game_state["timer"] < 0) {
                $(".TimerMinutes").addClass('text-danger');
            } else {
                $(".TimerMinutes").removeClass('text-danger');
            }


            // Game State
            $(".GameState").html(game_state["game_state_msg"]);

            if (!game_state["game_is_running"]){
                $('.start-game').removeClass('d-none');
                $('.pause-game-grp').addClass('d-none');
                $('.resume-game-grp').addClass('d-none');

                // Disable buttons when referee is not running
                $("#MidTimeChange").prop("disabled", true);
                $('.score-zone').each(function() {
                    $(this).find('.up-score').prop("disabled", true);
                    $(this).find('.down-score').prop("disabled", true);
                });
                $('.robot-penalty').each(function() {
                    $(this).find('.unpenalize').prop("disabled", true);
                    $(this).find('.penalize').prop("disabled", true);
                });
            }

            else if (game_state["game_is_running"]){
                $('.start-game').addClass('d-none');
                $('.pause-game-grp').removeClass('d-none'); 

                // Enable buttons when referee is running
                $("#MidTimeChange").prop("disabled", false);
                $('.score-zone').each(function() {
                    $(this).find('.up-score').prop("disabled", false);
                    $(this).find('.down-score').prop("disabled", false);
                });
                $('.robot-penalty').each(function() {
                    $(this).find('.unpenalize').prop("disabled", false);
                    $(this).find('.penalize').prop("disabled", false);
                });

                if (!game_state["game_is_not_paused"]){
                    $('.resume-game-grp').removeClass('d-none');
                    $('.pause-game-grp').addClass('d-none');
                }

                else if (game_state["game_is_not_paused"]) {
                    $('.pause-game-grp').removeClass('d-none');
                    $('.resume-game-grp').addClass('d-none');
                }
            }
 
            //Disable Pause Button if a Goal is waiting for Validation
            if (game_state["game_state_msg"] == "Waiting for Goal Validation"){
                $('.resume-game').prop("disabled", true);
            }
            else{
                $('.resume-game').prop("disabled", false);
            }
                


            // Referee History
            for (let history_entry of game_state["referee_history_sliced"]) {
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

            //Half Time Changes
            backend.HalfTimeChangeColorField(game_state["x_positive_goal"]);

            if (game_state["x_positive_goal"] === first_team){
                $('.robot-penalize-tab').css("flex-direction", "row");
            }
            else if (game_state["x_positive_goal"] === second_team){
                $('.robot-penalize-tab').css("flex-direction", "row-reverse");
            }
        });

    }, 200);

    $('.toast').toast('show');

    // Game Start&Stop
    $('.start-game').click(function() {
        backend.startGame();
        displayed_toast_nb = 0;
        $("#RefereeHistory").html('');
        $("#NoHistory").html('<h6 class="text-muted">No History</h6>');
    });

    $('.pause-game').click(function() {
        backend.pauseGame();
    });

    $('.resume-game').click(function() {
        backend.resumeGame();
    });

    $('.stop-game').click(function() {
        backend.stopGame();
    });

    
    // Half Time
    $('#MidTimeChange').click(function() {

        $("#RefereeHistory").append('<h5 class="text-muted m-3">Half Time</h5>');
        backend.startHalfTime();
    });

    $('#Y_ChangeCover').click(function() {
        $('.ChangeCover').addClass('d-none');
        $('.MidTimeIdentify').removeClass('d-none');
        $('.MidTimeIdentifyBefore').removeClass('d-none');
        backend.placeGame('swap_covers');
    });

    $('#N_ChangeCover').click(function() {
        backend.placeGame('gently_swap_side');
        backend.setTeamSides();
        $('.ChangeCover').addClass('d-none');
        $('.SecondHalfTime').removeClass('d-none');
        setTimeout(function() {
            backend.placeGame('standard');
        }, 5000);

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
        backend.setTeamSides();
        $('#HalfTimePlaceStd').removeClass('d-none');
        $('#Next_MidTimeIdentify').addClass('d-none');
        $('.MidTimeIdentifyDone').addClass('d-none');
        $('.MidTimeIdentify').addClass('d-none');
        $('.MidTimeIdentifyBefore').addClass('d-none');
        $('.SecondHalfTime').removeClass('d-none');
        backend.placeGame('standard');
    });

    $('#BtnSecondHalfTime').click(function() {
        setTimeout(function() {
        $('.ChangeCover').removeClass('d-none');
        $('.MidTimeIdentify').addClass('d-none');
        $('.SecondHalfTime').addClass('d-none');
        $('#HalfTimePlaceStd').addClass('d-none');
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

    $("#RefereeHistory").on('click','.validate-goal', function() {
        backend.getFullGameState(function(game_state) {
        last_referee_item = game_state["referee_history_sliced"].length-1
        id_last_referee_item = String(game_state["referee_history_sliced"][last_referee_item])
        nb = String(game_state["referee_history_sliced"].length-1)
        $("#toast-"+id_last_referee_item).find('.icon').removeClass('bi-circle-fill')
        $("#toast-"+id_last_referee_item).find('.icon').addClass('bi-check2-circle')
        $("#toast-"+id_last_referee_item).find('.toast-body').addClass('text-success')
        $("#toast-"+id_last_referee_item).find('.toast-body').html('<h5 class="m-0">Goal Validated</h5>')
        console.log(game_state["referee_history_sliced"])
        console.log(nb)
        });
        backend.validateGoal(true)
    });

    $("#RefereeHistory").on('click','.cancel-goal', function() {
        backend.getFullGameState(function(game_state) {
        last_referee_item = game_state["referee_history_sliced"].length-1
        id_last_referee_item = String(game_state["referee_history_sliced"][last_referee_item])
        $("#toast-"+id_last_referee_item).find('.icon').removeClass('bi-circle-fill')
        $("#toast-"+id_last_referee_item).find('.icon').addClass('bi-x-circle')
        $("#toast-"+id_last_referee_item).find('.toast-body').addClass('text-danger')
        $("#toast-"+id_last_referee_item).find('.toast-body').html('<h5 class="m-0">Goal Disallowed</h5>')
        });
        backend.validateGoal(false)
    });

    $('.reset-score').click(function() {
        backend.resetScore();
    });

    // Place Robots
    $('.strd-place').click(function() {
        backend.placeGame('standard');
    });

    $('.dots-place').click(function() {
        backend.placeGame('dots');
    });
    
    $('.side-place').click(function() {
        backend.placeGame('side');
    });
    
    // Robots Penalties
    $('.robot-penalty').each(function() {
        let robot_id = $(this).attr('rel');

        $(this).find('.penalize').click(function() {
            backend.addPenalty(5, robot_id);
        });
        $(this).find('.unpenalize').click(function() {
            backend.cancelPenalty(robot_id);
        });
    });
}