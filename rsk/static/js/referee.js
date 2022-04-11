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
            if (time[1]<10){
                $(".TimerMinutes").html(time[0]+":"+0+time[1]);
            }
            else 
            $(".TimerMinutes").html(time[0]+":"+time[1]);
        });

    }, 200);

    $('.toast').toast('show')

    $('.start-referee').click(function() {
        backend.startReferee();
        $('.PlcmPLayer').addClass('referee-running');
        $('.start-game').removeClass('disabled')
    });

    $('.stop-referee').click(function() {
        backend.stopGame();
        backend.stopReferee();
        $('.PlcmPLayer').removeClass('referee-running');
        $('.start-game').addClass('disabled');
        $('.start-game').removeClass('d-none');
        $('.resume-game-grp').addClass('d-none');
        $('.pause-game-grp').addClass('d-none');
    });

    $('.start-game').click(function() {
        backend.startGame();
        $('.start-game').addClass('d-none');
        $('.pause-game-grp').removeClass('d-none');
    });

    $('.pause-game').click(function() {
        backend.pauseGame();
    });

    $('.resume-game').click(function() {
        backend.resumeGame();
    });
    
    $('.pause-game').click(function() {
        $('.resume-game-grp').removeClass('d-none');
        $('.pause-game-grp').addClass('d-none');
    });

    $('.resume-game').click(function() {
        $('.pause-game-grp').removeClass('d-none');
        $('.resume-game-grp').addClass('d-none');
    });

    $('.stop-game').click(function() {
        backend.stopGame();
        $('.start-game').removeClass('d-none');
        $('.pause-game-grp').addClass('d-none');
        $('.resume-game-grp').addClass('d-none');
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
}