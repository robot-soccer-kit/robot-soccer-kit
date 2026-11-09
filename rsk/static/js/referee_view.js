// Display of the referee state (scoreboard, robots, history), shared by the live referee and the
// replay

// Readable texts for the penalty reasons and the tasks preempting the robots
const PENALTY_REASONS = {
    manually_penalized: 'Penalized by the referee',
    ball_abuse: 'Ball abuse (stayed too long near the ball)',
    abusive_attack: 'Abusive attack (in the opponent defense area)',
    abusive_defense: 'Abusive defense (two robots in the defense area)',
};

const PREEMPTION_REASONS = {
    'force-place': 'Being placed',
    'game-start': 'Waiting for the kick-off',
    'manually-paused': 'Game paused',
    'goal': 'Paused after a goal',
    'sideline-crossed': 'Ball out of the field',
    'half-time': 'Half time',
    'stop-all': 'Stopped',
    'emergency': 'Emergency stop',
};

function preemptionText(reason) {
    if (reason.startsWith('out-of-game')) {
        return 'Out of the field: going back';
    }
    if (reason.startsWith('penalty-')) {
        return 'Penalized';
    }
    return PREEMPTION_REASONS[reason] || reason;
}

function createRefereeView(constants) {
    const teams = constants.team_colors; // ["green", "blue"]
    const numbers = [1, 2];

    // Building the robots cards of each team
    for (let team of teams) {
        let html = '<div class="card-header d-flex align-items-center">'
            + '<span class="team-robots-name">' + capitalize(team) + '</span>'
            + '<span class="ms-auto small fw-normal opacity-75 team-robots-side"></span></div>'
            + '<div class="card-body py-1">';
        for (let number of numbers) {
            let robot = team + number;
            html += '<div class="robot-row robot-penalty" rel="' + robot + '">'
                + '<img src="static/imgs/robot' + robot + '.svg" alt="' + capitalize(team) + ' ' + number + '" />'
                + '<div class="robot-status">'
                + '<div class="robot-state">...</div>'
                + '<div class="progress invisible"><div class="progress-bar" style="width: 0%"></div></div>'
                + '</div>'
                + '<div class="btn-group replay-hide">'
                + '<button class="btn btn-sm btn-outline-team penalize" type="button" disabled'
                + ' title="Penalize this robot for ' + constants.default_penalty + ' s">'
                + '<i class="bi bi-hourglass-split"></i> ' + constants.default_penalty + ' s</button>'
                + '<button class="btn btn-sm btn-outline-secondary unpenalize" type="button" disabled'
                + ' title="Cancel the penalty"><i class="bi bi-x-lg"></i></button>'
                + '</div>'
                + '</div>';
        }
        html += '</div>';
        $('.team-robots.team-' + team).html(html);
    }

    // Teams are displayed on the side of the field they defend: the team defending the goal on the
    // negative x side is on the left (as on the field image)
    function updateSides(game_state) {
        let left = teams.find(team => !game_state.teams[team].x_positive) || teams[0];
        for (let team of teams) {
            let isLeft = team == left;
            $('.scoreboard .team-block[data-team="' + team + '"]')
                .css('order', isLeft ? 0 : 2)
                .toggleClass('is-left', isLeft)
                .toggleClass('is-right', !isLeft);
            $('.team-robots-col[data-team="' + team + '"]').css('order', isLeft ? 0 : 1);
            $('.team-' + team + ' .team-robots-side').text(isLeft ? 'left side' : 'right side');
        }
        $('.scoreboard .game-center').css('order', 1);
    }

    function updateTimer(game_state) {
        let timer = game_state.timer;
        let running = game_state.game_is_running && !game_state.game_paused;
        $('.TimerMinutes').text(formatTimer(timer));
        $('.scoreboard .timer')
            .toggleClass('overtime', running && timer < 0)
            .toggleClass('ending', running && timer >= 0 && timer <= 10);
    }

    function robotState(robot, game_state) {
        if (robot.penalized) {
            let reason = PENALTY_REASONS[robot.penalized_reason] || robot.penalized_reason || 'Penalized';
            return {
                text: '<i class="bi bi-hourglass-split"></i> ' + escapeHtml(reason)
                    + ' <span class="fw-semibold">(' + robot.penalized_remaining + ' s)</span>',
                cls: 'text-danger',
                progress: Math.min(100, robot.penalized_remaining * 100 / constants.default_penalty),
            };
        }
        let reasons = (robot.preemption_reasons || []).filter(reason => !reason.startsWith('penalty-'));
        if (reasons.length) {
            return {
                text: '<i class="bi bi-pause-circle"></i> '
                    + escapeHtml([...new Set(reasons.map(preemptionText))].join(', ')),
                cls: 'text-body-secondary',
                progress: null,
            };
        }
        if (game_state.game_is_running && !game_state.game_paused) {
            return { text: '<i class="bi bi-play-circle"></i> Playing', cls: 'text-success', progress: null };
        }
        return { text: '<i class="bi bi-check-circle"></i> Ready', cls: '', progress: null };
    }

    function updateRobots(game_state, live) {
        let canPenalize = live && game_state.game_is_running;
        for (let team of teams) {
            for (let number of numbers) {
                let robot = (game_state.teams[team].robots || {})[number];
                let row = $('.robot-penalty[rel="' + team + number + '"]');
                if (!robot) {
                    continue;
                }
                let state = robotState(robot, game_state);
                row.find('.robot-state')
                    .html(state.text)
                    .attr('title', row.find('.robot-state').text())
                    .removeClass('text-danger text-success text-body-secondary')
                    .addClass(state.cls);
                row.find('.progress').toggleClass('invisible', state.progress === null);
                if (state.progress !== null) {
                    row.find('.progress-bar').css('width', state.progress + '%');
                }
                row.find('.penalize').prop('disabled', !canPenalize);
                row.find('.unpenalize').prop('disabled', !canPenalize || !robot.penalized);
            }
        }
    }

    // Renders the game state (as given by the referee)
    function render(game_state, options = {}) {
        let live = options.live !== false;

        updateSides(game_state);
        updateTimer(game_state);
        $('.GameState').text(game_state.game_state_msg || '');

        for (let team of teams) {
            let block = $('.scoreboard .team-block[data-team="' + team + '"]');
            block.find('.score').text(game_state.teams[team].score);
            let input = block.find('.team-name');
            if (!input.is(':focus')) {
                input.val(game_state.teams[team].name || '');
            }
            block.find('.up-score, .down-score').prop('disabled', !live || !game_state.game_is_running);
        }

        updateRobots(game_state, live);
    }

    // Renders the referee history: list of [number, timer, team, event]. Goal decisions are shown
    // on the goal they concern. pendingGoal: the last goal is waiting for validation (buttons are
    // shown). outcomes: decisions known otherwise (old replays), by goal number.
    function renderHistory(history, options = {}) {
        let container = $('#RefereeHistory');
        let outcomes = Object.assign({}, options.outcomes || {});
        let entries = [];

        for (let [num, timer, team, event] of history) {
            if (event == 'Goal validated' || event == 'Goal cancelled') {
                // Concerns the last goal of this team
                for (let k = entries.length - 1; k >= 0; k--) {
                    if (entries[k].event == 'Goal' && entries[k].team == team) {
                        outcomes[entries[k].num] = event == 'Goal validated';
                        break;
                    }
                }
                continue;
            }
            entries.push({ num, timer, team, event });
        }

        let lastGoal = [...entries].reverse().find(entry => entry.event == 'Goal');
        let html = '';
        for (let entry of entries) {
            let isTeam = teams.includes(entry.team);
            html += '<div class="history-entry' + (isTeam ? ' team-' + entry.team : '') + '" data-num="' + entry.num + '">'
                + '<span class="history-time">' + formatTimer(entry.timer) + '</span>'
                + '<span class="history-event">';
            if (entry.event == 'Goal') {
                html += '<i class="bi bi-trophy-fill text-team"></i> Goal for '
                    + '<span class="history-team">' + escapeHtml(options.teamNames?.[entry.team] || capitalize(entry.team)) + '</span>';
            } else if (entry.event == 'Sideline crossed') {
                html += '<i class="bi bi-box-arrow-up-right"></i> Ball out of the field';
            } else {
                html += escapeHtml(entry.event);
            }
            html += '</span>';

            if (entry.event == 'Goal') {
                if (entry.num in outcomes) {
                    html += outcomes[entry.num]
                        ? '<span class="badge text-bg-success"><i class="bi bi-check-lg"></i> Validated</span>'
                        : '<span class="badge text-bg-danger"><i class="bi bi-x-lg"></i> Cancelled</span>';
                } else if (options.pendingGoal && entry === lastGoal) {
                    html += '<span class="btn-group">'
                        + '<button class="btn btn-sm btn-success validate-goal" type="button"><i class="bi bi-check-lg"></i> Validate</button>'
                        + '<button class="btn btn-sm btn-outline-danger cancel-goal" type="button"><i class="bi bi-x-lg"></i> Cancel</button>'
                        + '</span>';
                }
            }
            html += '</div>';
        }

        if (!entries.length) {
            html = '<div class="text-body-secondary text-center history-empty">No event yet</div>';
        }

        // Only updating when something changed (keeps the scroll and the buttons focus)
        if (container.data('html') !== html) {
            let atBottom = container[0].scrollHeight - container.scrollTop() - container.innerHeight() < 30;
            container.html(html).data('html', html);
            if (atBottom || options.scrollToEnd) {
                container.scrollTop(container[0].scrollHeight);
            }
        }
    }

    return { render, renderHistory };
}
