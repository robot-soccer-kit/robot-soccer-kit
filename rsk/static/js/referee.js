function referee_initialize(backend)
{
    setInterval(function() {
        backend.getScore("blue", function(score) {
            $( "#BlueScore" ).html(score);
        });

        backend.getScore("green", function(score) {
            $( "#GreenScore" ).html(score);
        });

    }, 200);


    $('.start-referee').click(function() {
        backend.startReferee();
        $('.PlcmPLayer').addClass('referee-running');
    });

    $('.stop-referee').click(function() {
        backend.stopReferee();
        // backend.stopMatch();
        $('.PlcmPLayer').removeClass('referee-running');
    });

    $('.start-match').click(function() {
        // backend.startMatch();
        $('.PlcmPLayer').addClass('match-running');
        $('.start-match').addClass('d-none')
        $('.match-pause-stop').removeClass('d-none')
    });

    $('.pause-match').click(function() {
        // backend.pauseMatch();
    });

    $('.stop-match').click(function() {
        // backend.stopMatch();
        $('.PlcmPLayer').removeClass('match-running');
        $('.start-match').removeClass('d-none')
        $('.match-pause-stop').addClass('d-none')
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