function referee_initialize(backend)
{
    setInterval(function() {
        backend.getScore("blue", function(score) {
            $( "#BlueScore" ).html(score);
        });

        backend.getScore("green", function(score) {
            $( "#GreenScore" ).html(score);
        });

        backend.getTimer(function(time) {
            if (time[2] == "neg" && time[0]==0){
                if (time[1]<10){
                    $(".TimerMinutes").html("-"+time[0]+":"+0+time[1]);
                }
                else 
                $(".TimerMinutes").html("-"+time[0]+":"+time[1]);
            }
            else{
                if (time[1]<10){
                    $(".TimerMinutes").html(time[0]+":"+0+time[1]);
                }
                else 
                $(".TimerMinutes").html(time[0]+":"+time[1]);
            }
            if (time[2] == "neg"){
                $(".TimerMinutes").addClass('text-danger')
            }
            else{
                $(".TimerMinutes").removeClass('text-danger')
            }
        });

        backend.getGameState(function(game_state) {
            $(".GameState").html(game_state);
        });

        backend.getRefereeHistory(3, function(history) {
            for (let pas = 0; pas < 3; pas++) {
                if (history[pas] != undefined){
                    $(" #NoHistory ").html('')
                    if (history[pas][0] >= displayed_toast_nb) {
                        [num, minutes, secondes, team, referee_event] = history[pas]
                        let htmlStr = ''

                        if (secondes<10){
                            secondes = '0' + secondes
                        }

                        if (team == 'neutral'){
                            htmlStr += '<div id="toast' +displayed_toast_nb+ '" class="toast ' +team+ '-toast-position" role="alert" aria-live="assertive" aria-atomic="true"data-bs-autohide="false">'
                            htmlStr += '  <div class="toast-header">'
                            htmlStr += '    <i class="bi bi-circle-fill"></i>&nbsp;&nbsp;'
                            htmlStr += '    <strong class="me-auto">' +referee_event+ '</strong>'
                            htmlStr += '    <small class="text-muted">' +minutes+ ':' +secondes+ '</small>'
                            htmlStr += '  </div>'
                            htmlStr += '  <div class="toast-body">'
                            htmlStr += referee_event
                            htmlStr += '  </div>'
                            htmlStr += '</div>'
                        }
                        else{
                            htmlStr += '<div id="toast' +displayed_toast_nb+ '" class="toast ' +team+ '-toast-position border-' +team+ '" role="alert" aria-live="assertive" aria-atomic="true"data-bs-autohide="false">'
                            htmlStr += '  <div class="toast-header bg-head-' +team+ '">'
                            htmlStr += '    <i class="bi bi-circle-fill text-white"></i>&nbsp;&nbsp;'
                            htmlStr += '    <strong class="me-auto text-light">' +referee_event+ ' ' +team+ ' Team</strong>'
                            htmlStr += '    <small class="text-white">' +minutes+ ':' +secondes+ '</small>'
                            htmlStr += '  </div>'
                            htmlStr += '  <div class="toast-body bg-body-' +team+ '">'
                            htmlStr += referee_event
                            htmlStr += '  </div>'
                            htmlStr += '</div>'
                        }

                        $("#RefereeHistory").append(htmlStr)
                        $('#toast'+displayed_toast_nb).toast('show')
                        $("#tchat").scrollTop($("#tchat")[0].scrollHeight);

                        displayed_toast_nb = displayed_toast_nb+1

                    }
                }

            }
        });

    }, 200);

    var displayed_toast_nb = 0 

    $('.toast').toast('show')

    $('.start-game').click(function() {
        backend.startGame();
        $('.start-game').addClass('d-none');
        $('.pause-game-grp').removeClass('d-none');   

        displayed_toast_nb = 0
        $("#RefereeHistory").html('')
        $("#NoHistory").html('<h6 class="text-muted">No History</h6>')
        $("#MidTimeChange").prop("disabled", false)
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
        $("#MidTimeChange").prop("disabled", true)
    });

    $('#MidTimeChange').click(function() {
        backend.MidTimeChangeColorField()
        backend.setTeamSides()
        let XposPenaltyHTML = $('#XposPenalty').html()
        let XnegPenaltyHTML = $('#XnegPenalty').html()
        $('#XposPenalty').html(XnegPenaltyHTML)
        $('#XnegPenalty').html(XposPenaltyHTML)
        $("#RefereeHistory").append('<h5 class="text-muted m-3">Half Time</h5>')
        backend.startHalfTime()
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
        backend.startSecondHalfTime()
    });

    $('.edit-teams-name').click(function() {
        $('.edit-teams-name').addClass('d-none')
        $('.validate-teams-name').removeClass('d-none')

        $( "#BlueTeamNameInput" ).removeClass('d-none')
        $( "#GreenTeamNameInput" ).removeClass('d-none')
        $( "#BlueTeamNameDisplay" ).addClass('d-none')
        $( "#GreenTeamNameDisplay" ).addClass('d-none')
    });

    $('.validate-teams-name').click(function() {
        let $BlueTeamName = $( "#BlueTeamNameInput" ).val()
        let $GreenTeamName = $( "#GreenTeamNameInput" ).val()
        $( "#BlueTeamNameDisplay" ).html($BlueTeamName)
        $( "#GreenTeamNameDisplay" ).html($GreenTeamName)

        $('.edit-teams-name').removeClass('d-none')
        $('.validate-teams-name').addClass('d-none')
        $( "#BlueTeamNameInput" ).addClass('d-none')
        $( "#GreenTeamNameInput" ).addClass('d-none')
        $( "#BlueTeamNameDisplay" ).removeClass('d-none')
        $( "#GreenTeamNameDisplay" ).removeClass('d-none')
    });

    $('.blue-up-score').click(function() {
        backend.updateScore("blue", 1)
    });

    $('.blue-down-score').click(function() {
        backend.updateScore("blue", -1)
    });

    $('.green-up-score').click(function() {
        backend.updateScore("green", 1)
    });

    $('.green-down-score').click(function() {
        backend.updateScore("green", -1)
    });

    $('.reset-score').click(function() {
        backend.resetScore()
    });

    $(' #Strd-place ').click(function() {
        backend.placeGame();
    });
    
}