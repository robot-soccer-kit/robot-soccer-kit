// Scheduler mode: games retrieved from a scheduler server, scores published to it

function scheduler_initialize(backend, url) {
    let games = [];
    let currentGame = null;
    let currentPublished = false;
    // Games published from this page (they stay published when the games are refreshed)
    let publishedGames = new Set();

    function gameById(gameId) {
        return games.find(game => String(game.id) == String(gameId)) || null;
    }

    function setTeam(color, name, key) {
        $('.team-name[rel="' + color + '"]').val(name).change();
        $('.key-' + color).val(key).change();
    }

    function setCurrentGame(gameId) {
        currentGame = gameById(gameId);
        currentPublished = currentGame !== null && publishedGames.has(String(currentGame.id));
        $('.scheduler-game-row').removeClass('scheduler-game-row-selected');

        if (currentGame) {
            $('.scheduler-game-row[data-game-id="' + currentGame.id + '"]').addClass('scheduler-game-row-selected');
            if (currentGame.teamBlue) {
                setTeam('blue', currentGame.teamBlue.name, currentGame.teamBlue.token);
            }
            if (currentGame.teamGreen) {
                setTeam('green', currentGame.teamGreen.name, currentGame.teamGreen.token);
            }
            updateScores();
        }
    }

    function row(gameId) {
        return $('.scheduler-game-row[data-game-id="' + gameId + '"]');
    }

    // The scores of the active game are the ones of the referee
    function updateScores() {
        if (currentGame && !currentPublished) {
            backend.get_game_state(function (game_state) {
                row(currentGame.id).find('.score-blue').text(game_state.teams.blue.score);
                row(currentGame.id).find('.score-green').text(game_state.teams.green.score);
            });
        }
    }
    setInterval(updateScores, 1000);

    function uploadReplay(gameId) {
        function tryFetch(retries = 10) {
            fetch('http://' + document.location.host + '/api/recorded_data')
                .then(response => {
                    if (!response.ok) {
                        if (retries > 0) {
                            setTimeout(() => tryFetch(retries - 1), 200);
                        } else {
                            console.error('No recorded data available after retries');
                        }
                        return;
                    }
                    return response.blob();
                })
                .then(blob => {
                    if (!blob) return;
                    const formData = new FormData();
                    formData.append('replay', blob, 'replay.json.gz');
                    return $.ajax({
                        url: url + '/upload-replay/' + gameId,
                        method: 'POST',
                        data: formData,
                        processData: false,
                        contentType: false,
                    });
                })
                .then(data => {
                    if (data === true) console.log('Replay uploaded');
                })
                .catch(error => console.error('Error uploading replay:', error));
        }

        // Waiting for the record to be written
        setTimeout(() => tryFetch(), 500);
    }

    $('.scheduler-teams').on('click', '.scheduler-load-game', function () {
        setCurrentGame($(this).closest('tr').attr('data-game-id'));
    });

    $('.scheduler-teams').on('click', '.scheduler-publish-game', function () {
        let gameId = $(this).closest('tr').attr('data-game-id');
        let scoreBlue = row(gameId).find('.score-blue').text();
        let scoreGreen = row(gameId).find('.score-green').text();

        if (scoreBlue == '?' || scoreGreen == '?') {
            notify('Set this game active and play it before publishing its scores', 'warning');
            return;
        }

        confirmDialog('Publish the score ' + scoreGreen + ' - ' + scoreBlue + ' (green - blue)? The game will be ended.', function () {
            $.get(url + '/publish/' + gameId + '/' + scoreBlue + '/' + scoreGreen, function (data) {
                if (data === true) {
                    backend.stop_game();
                    publishedGames.add(String(gameId));
                    row(gameId).find('.scheduler-actions').html('<span class="badge text-bg-success">Published</span>');
                    uploadReplay(gameId);
                    if (currentGame && String(currentGame.id) == String(gameId)) {
                        currentPublished = true;
                    }
                    notify('Score published', 'success', 3000);
                } else {
                    notify('The score could not be published', 'danger');
                }
            }).fail(function () {
                notify('The scheduler server can not be reached', 'danger');
            });
        }, 'Publish');
    });

    function refreshGames() {
        $('.scheduler-teams').html('<tr><td colspan="6" class="text-center text-body-secondary py-4">Loading...</td></tr>');

        $.get(url + '/games', function (all_games) {
            games = all_games || [];
            let html = '';

            for (let game of games) {
                let date = new Date(game.timeSlot.begin);
                html += '<tr class="scheduler-game-row" data-game-id="' + escapeHtml(game.id) + '">'
                    + '<td class="ps-3">' + escapeHtml(date.toLocaleString()) + '</td>'
                    + '<td class="text-end team-green"><span class="text-team fw-semibold">' + escapeHtml(game.teamGreen ? game.teamGreen.name : '?') + '</span></td>'
                    + '<td class="text-center fw-bold">'
                    + '<span class="team-green"><span class="text-team score-green">?</span></span>'
                    + ' - '
                    + '<span class="team-blue"><span class="text-team score-blue">?</span></span>'
                    + '</td>'
                    + '<td class="team-blue"><span class="text-team fw-semibold">' + escapeHtml(game.teamBlue ? game.teamBlue.name : '?') + '</span></td>'
                    + '<td><small class="text-body-secondary">' + escapeHtml(game.comment || '') + '</small></td>'
                    + '<td class="text-end pe-3 scheduler-actions text-nowrap">'
                    + '<button class="btn btn-sm btn-outline-primary scheduler-load-game" type="button">Set active</button> '
                    + '<button class="btn btn-sm btn-success scheduler-publish-game" type="button">Publish</button>'
                    + '</td>'
                    + '</tr>';
            }
            if (!html) {
                html = '<tr><td colspan="6" class="text-center text-body-secondary py-4">No games scheduled</td></tr>';
            }
            $('.scheduler-teams').html(html);
            for (let gameId of publishedGames) {
                row(gameId).find('.scheduler-actions').html('<span class="badge text-bg-success">Published</span>');
            }

            if (currentGame) {
                setCurrentGame(currentGame.id);
            }
        }).fail(function () {
            $('.scheduler-teams').html('<tr><td colspan="6" class="text-center text-danger py-4">The scheduler server can not be reached</td></tr>');
        });
    }

    refreshGames();
    $('.scheduler-refresh-games').click(refreshGames);
}
