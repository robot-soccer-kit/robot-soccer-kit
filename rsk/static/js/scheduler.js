function scheduler_initialize(backend, url) {
    $.get('static/scheduler_team.html', function (team_template) {
        let games = {};
        let currentGame = null;

        function setCurrentGame(gameId) {
            currentGame = null
            $('.scheduler-game-row').removeClass('scheduler-game-row-selected');

            for (let game of games) {
                if (game.id == gameId) {
                    $('.scheduler-game-row-'+gameId).addClass('scheduler-game-row-selected');
                    if (game.teamBlue) {
                        setTeam('blue', game.teamBlue.name, game.teamBlue.token);
                    }
                    if (game.teamGreen) {
                        setTeam('green', game.teamGreen.name, game.teamGreen.token);
                    }
                    currentGame = game;
                    updateScores()
                }
            }
        }

        function updateScores() {
            if (currentGame) {
                backend.get_game_state(function(game_state) {
                    $('.scheduler-score-blue-'+currentGame.id).text(game_state.teams.blue.score)
                    $('.scheduler-score-green-'+currentGame.id).text(game_state.teams.green.score)
                });
            }
        }
        setInterval(updateScores, 1000)

        function setTeam(color, name, key) {
            $(".team-name[rel=" + color + "]").val(name)
            $(".key-" + color).val(key);
            $(".key-" + color).change();
        }

        function setupListeners() {
            $('.scheduler-load-game').click(function () {
                let gameId = $(this).attr('data-game-id');
                setCurrentGame(gameId);
                return false;
            });

            $('.scheduler-publish-game').click(function() {
                let gameId = $(this).attr('data-game-id');
                let scoreBlue = $('.scheduler-score-blue-'+gameId).text();
                let scoreGreen = $('.scheduler-score-green-'+gameId).text();

                if (scoreBlue == "?" || scoreGreen == "?") {
                    alert('Please enter scores for both teams');
                    return;
                } else {
                    $.get(url + '/publish/'+gameId+'/'+scoreBlue+'/'+scoreGreen, function (data) {
                        if (data === true) {
                            $('.scheduler-actions-'+gameId).text('Published!');
                            if (currentGame == gameId) {
                                setCurrentGame(null)
                            }
                        }
                    });
                }
                return false;
            });
        }

        function refreshGames() {
            $('.scheduler-teams').html('Loading...');

            $.get(url + '/games', function (all_games) {
                if (all_games) {
                    games = all_games;
                    let html = ''

                    for (let game of games) {
                        let game_html = team_template
                        date = new Date(game.timeSlot.begin);
                        game_html = game_html.replace('{time}', date.toLocaleString());
                        if (game.teamBlue) {
                            game_html = game_html.replace('{teamBlue}', game.teamBlue.name);
                        } else {
                            game_html = game_html.replace('{teamBlue}', '?')
                        }
                        if (game.teamGreen) {
                            game_html = game_html.replace('{teamGreen}', game.teamGreen.name);
                        } else {
                            game_html = game_html.replace('{teamGreen}', '?')
                        }
                        game_html = game_html.replace('{comment}', game.comment);
                        game_html = game_html.replace(/{id}/g, game.id);

                        html += game_html
                    }


                    $('.scheduler-teams').html(html);
                    setupListeners();
                } else {
                    $('.scheduler-teams').html('No games scheduled');
                }
            });

            return false;
        }

        refreshGames()

        $('.scheduler-refresh-games').click(refreshGames)
    });
}