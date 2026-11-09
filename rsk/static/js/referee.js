// Live referee: game controls, scores, penalties, half time and history

function referee_initialize(backend, constants) {
    const view = createRefereeView(constants);
    let history = [];
    let historyLastNum = null;
    let gameState = null;

    function updateHistory(game_state) {
        // The game state only contains the last events: the whole history is retrieved when it
        // changes
        let sliced = game_state.referee_history_sliced || [];
        let lastNum = sliced.length ? sliced[sliced.length - 1][0] : -1;
        let options = {
            pendingGoal: game_state.game_state_msg == 'Waiting for Goal Validation',
            teamNames: {
                green: game_state.teams.green.name,
                blue: game_state.teams.blue.name,
            },
        };

        if (lastNum !== historyLastNum) {
            historyLastNum = lastNum;
            backend.get_referee_history(function (full_history) {
                history = full_history;
                view.renderHistory(history, Object.assign({ scrollToEnd: true }, options));
            });
        } else {
            view.renderHistory(history, options);
        }
    }

    function updateControls(game_state) {
        let running = game_state.game_is_running;
        let paused = game_state.game_paused;

        $('.start-game').toggleClass('d-none', running);
        $('.running-game-controls').toggleClass('d-none', !running);
        $('.pause-game').toggleClass('d-none', paused);
        $('.resume-game').toggleClass('d-none', !paused);
        // A goal must be validated or cancelled before resuming
        $('.resume-game').prop('disabled', game_state.game_state_msg == 'Waiting for Goal Validation');
        $('.half-time').prop('disabled', !running);

        // The recording settings can't be changed during a game
        $('.enable-rec-settings input').prop('disabled', running);
        $('.recording-locked').toggleClass('d-none', !running);
    }

    function update() {
        backend.get_game_state(function (game_state) {
            gameState = game_state;
            view.render(game_state, { live: true });
            updateControls(game_state);
            updateHistory(game_state);
        });
    }

    setInterval(update, 200);
    update();

    // Game
    $('.start-game').click(function () {
        backend.start_game();
    });
    $('.pause-game').click(function () {
        backend.pause_game();
    });
    $('.resume-game').click(function () {
        backend.resume_game();
    });
    $('.stop-game').click(function () {
        backend.stop_game();
    });

    // Teams names and scores
    $('.team-name').change(function () {
        backend.set_team_name($(this).attr('rel'), $(this).val());
    });
    $('.scoreboard .team-block').each(function () {
        let team = $(this).data('team');
        $(this).find('.up-score').click(function () {
            backend.increment_score(team, 1);
        });
        $(this).find('.down-score').click(function () {
            backend.increment_score(team, -1);
        });
    });

    // Goals validation
    $('#RefereeHistory').on('click', '.validate-goal', function () {
        $(this).closest('.btn-group').find('.btn').prop('disabled', true);
        backend.validate_goal(true, update);
    });
    $('#RefereeHistory').on('click', '.cancel-goal', function () {
        $(this).closest('.btn-group').find('.btn').prop('disabled', true);
        backend.validate_goal(false, update);
    });

    // Robots placement
    $('.place').click(function () {
        backend.place_game($(this).data('configuration'));
    });

    // Penalties
    $('.page-referee').on('click', '.robot-penalty .penalize', function () {
        backend.add_penalty(constants.default_penalty, $(this).closest('.robot-penalty').attr('rel'));
    });
    $('.page-referee').on('click', '.robot-penalty .unpenalize', function () {
        backend.cancel_penalty($(this).closest('.robot-penalty').attr('rel'));
    });

    // Half time
    function halfTimeStep(step) {
        $('#half-time-modal .half-time-step').addClass('d-none');
        $('#half-time-modal .half-time-step[data-step="' + step + '"]').removeClass('d-none');
    }

    function placeForSecondHalf() {
        backend.swap_team_sides(function () {
            backend.place_game('standard');
        });
        halfTimeStep('second-half');
    }

    $('#half-time-modal').on('show.bs.modal', function () {
        backend.start_half_time();
        halfTimeStep('covers');
        $('.half-time-identify').removeClass('d-none').prop('disabled', false);
        $('.half-time-identified, .half-time-identifying').addClass('d-none');
    });

    $('.half-time-swap-covers').click(function () {
        backend.place_game('swap_covers', true);
        halfTimeStep('identify');
    });

    $('.half-time-keep-covers').click(function () {
        backend.place_game('gently_swap_side');
        placeForSecondHalf();
    });

    $('.half-time-identify').click(function () {
        $(this).prop('disabled', true);
        $('.half-time-identifying').removeClass('d-none');
        backend.identify(function () {
            $('.half-time-identifying, .half-time-identify').addClass('d-none');
            $('.half-time-identified').removeClass('d-none');
        });
    });

    $('.half-time-identified').click(placeForSecondHalf);

    $('.half-time-second-half').click(function () {
        backend.start_second_half_time();
    });
}
