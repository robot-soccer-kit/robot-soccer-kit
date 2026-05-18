function replay_initialize(backend) {

    let displayed_toast_nb = 0;

    let event_neutral_tpl = '';
    $.get('/static/referee_event_neutral.html', function (data) {
        event_neutral_tpl = data;
    });
    let event_team_tpl = ''
    $.get('/static/referee_event_team.html', function (data) {
        event_team_tpl = data;
    });

    $('.detection-view').css("display", 'none')
    $('.commands-view').css("display", 'none')


    $('.team-name').prop('disabled', true)

    // $('.robot-penalize-tab .first-team-name').html("detection state")
    // $('.robot-penalize-tab .second-team-name').html("detection state")

    // $('.robot-penalty').addClass("justify-content-around")

    fetch("/api/replay_data")
        .then(response => response.json())
        .then(logs => {
            console.log(document.getElementById('back').offsetWidth)
            console.log(document.getElementById('back').offsetHeight)
            console.log(document.getElementById('back').width)
            console.log(document.getElementById('back').height)

            backend.constants(function (constants) {
                const renderer = createFieldRenderer(constants)
                $(window).on("resize", renderer.resizeCanvases)


                const markers = {}
                for (const key of ["blue1", "blue2", "green1", "green2"]) {
                    markers[key] = { image: new Image(), pos: [0, 0, 0], leds: [0, 0, 0] }
                    markers[key].image.src = "static/imgs/robot" + key + ".png"
                }

                const positionIndexes = { ball: 0, green1: 0, green2: 0, blue1: 0, blue2: 0 }
                const ledsIndexes = { green1: 0, green2: 0, blue1: 0, blue2: 0 }
                const refereeIndexes = { game_is_running: 0, game_paused: 0, timer: 0, game_state_msg: 0, teams: 0, referee_history_sliced: 0, validate_goal: 0 }
                const detectionIndexes = { green1: 0, green2: 0, blue1: 0, blue2: 0, c1:0, c2:0, c3:0, c4:0 }
                const commandsIndexes = { green1: 0, green2: 0, blue1: 0, blue2: 0 }

                const allSeries = [
                    logs.positions?.ball, logs.positions?.green1, logs.positions?.green2,
                    logs.positions?.blue1, logs.positions?.blue2
                ].filter(Boolean)
                const startTimestamp = allSeries.reduce((min, s) => Math.min(min, s[0].timestamp), Infinity)
                const endTimestamp = allSeries.reduce((max, s) => Math.max(max, s.at(-1).timestamp), 0)

                let isRunning = false
                let frameId = null
                let wallStart = null
                let logStart = startTimestamp
                let currentTimestamp = 0

                function advance(series, indexes, key, t) {
                    if (!series?.length) return null
                    while (indexes[key] + 1 < series.length && series[indexes[key] + 1].timestamp <= t) {
                        indexes[key]++
                    }
                    return series[indexes[key]]?.timestamp <= t ? series[indexes[key]].data : null
                }

                function validationGoal(current_history, t) {
                    last_index_validation = refereeIndexes.validate_goal
                    serie_validate_goal = logs.referee?.validate_goal
                    if (!serie_validate_goal?.length) return null

                    if (last_index_validation < serie_validate_goal.length
                        && serie_validate_goal[last_index_validation].timestamp <= t
                    ) {
                        is_validated = serie_validate_goal[last_index_validation].data

                        last_referee_item = current_history.length - 1
                        id_last_referee_item = String(last_referee_item)
                        $('#toast-' + id_last_referee_item + ' .toast-body').show()
                        if (is_validated) {
                            // nb = String(logs.referee?.["referee_history_sliced"].length-1)
                            $("#toast-" + id_last_referee_item).find('.icon').removeClass('bi-circle-fill')
                            $("#toast-" + id_last_referee_item).find('.icon').addClass('bi-check2-circle')
                            $("#toast-" + id_last_referee_item).find('.toast-body').addClass('text-success')
                            $("#toast-" + id_last_referee_item).find('.toast-body').html('<h5 class="m-0">Goal Validated</h5>')
                        }
                        else {
                            $("#toast-" + id_last_referee_item).find('.icon').removeClass('bi-circle-fill')
                            $("#toast-" + id_last_referee_item).find('.icon').addClass('bi-x-circle')
                            $("#toast-" + id_last_referee_item).find('.toast-body').addClass('text-danger')
                            $("#toast-" + id_last_referee_item).find('.toast-body').html('<h5 class="m-0">Goal Disallowed</h5>')
                        }
                        refereeIndexes.validate_goal++
                    }

                }

                function updateReferee(referee_state) {
                    $('.GameState').html(referee_state.game_state_msg)
                    $('#GreenScore').html(referee_state.teams["green"]["score"])
                    $('#BlueScore').html(referee_state.teams["blue"]["score"])
                    $('.team-name[rel="green"]').val(referee_state.teams["green"]["name"])
                    $('.team-name[rel="blue"]').val(referee_state.teams["blue"]["name"])
                    $('.TimerMinutes').html(formatTimer(referee_state.timer))
                    $('.PlayerName[rel="green"]').val(referee_state.teams["green"]["name"]);
                    $('.PlayerName[rel="blue"]').val(referee_state.teams["blue"]["name"]);

                    // Referee history
                    for (let history_entry of referee_state["referee_history_sliced"]) {
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

                            if (team === 'neutral') {
                                html = event_neutral_tpl
                            } else {
                                html = event_team_tpl
                            }

                            for (let key in vars) {
                                html = html.replaceAll('{' + key + '}', vars[key])
                            }

                            $("#RefereeHistory").append(html);
                            $('#toast-' + displayed_toast_nb + ' .toast-body').css("display", 'none')
                            $('#toast-' + displayed_toast_nb).toast('show');
                            $("#tchat").scrollTop($("#tchat")[0].scrollHeight);

                            displayed_toast_nb = displayed_toast_nb + 1;

                        }
                    }

                }

                function updateDetection(detection_state) {
                    // if ($('.detection-value').hasClass("bg-body-grey")) {
                    //     $('.detection-value').removeClass("bg-body-grey")
                    // }
                    for (const [key, is_detected] of Object.entries(detection_state)) {
                        if (is_detected) {
                            $('.detection-tab td[rel="' + key + '"]').removeClass("text-bg-danger").addClass("bg-success")
                            .html("OK")
                        } else {
                            $('.detection-tab td[rel="' + key + '"]').removeClass("bg-success").addClass("text-bg-danger")
                            .html("Not det.")
                        }
                    }
                }

                function updateCommands(current_commands, t) {
                    for (const [key, value] of Object.entries(current_commands)) {
                        if (!value) continue
                        let [command_name, ...args] = value["received"]
                        let response = value["response"] //ex ["ok", true]
                        let is_master = value["master"]

                        // console.log(logs.command_received[key][commandsIndexes[key]])
                        // let age = (t - logs.command_received[key][commandsIndexes[key]]?.timestamp).toPrecision(5)
                        const currentEntry = logs.command_received[key][commandsIndexes[key]]
                        const age = (t - currentEntry?.timestamp).toFixed(4)

                        let str_command = command_name + "(" + args.map(a => a.toPrecision(3)).join(", ") + ")"

                        if (is_master) {
                            str_command += " *master"
                        }

                        $('.commands-tab .command[rel="' + key + '"]').html(str_command)
                        $('.commands-tab .response[rel="' + key + '"]').html(response[1])
                        if (age < 5) {
                            $('.commands-tab .age[rel="' + key + '"]').html(age)
                        } else {
                            $('.commands-tab .age[rel="' + key + '"]').html(" > 5")
                        }
                        

                        // cells color
                        console.log(response, key)
                        if (!response[0]) {
                            $('.commands-tab .response[rel="' + key + '"]').removeClass("text-bg-success").addClass("text-bg-danger")
                        } else {
                            $('.commands-tab .response[rel="' + key + '"]').removeClass("text-bg-danger").addClass("text-bg-success")
                        }
                        if (age < 0.5) {
                            $('.commands-tab .age[rel="' + key + '"]').removeClass("text-bg-danger").removeClass("text-bg-warning").addClass("text-bg-success")
                        } else if (age >= 0.5 && age <= 5) {
                            $('.commands-tab .age[rel="' + key + '"]').removeClass("text-bg-success").removeClass("text-bg-danger").addClass("text-bg-warning")
                        } else {
                            $('.commands-tab .age[rel="' + key + '"]').removeClass("text-bg-success").removeClass("text-bg-warning").addClass("text-bg-danger")
                        }

                    }
                }

                function loop() {
                    const elapsed = (performance.now() - wallStart) / 1000
                    const t = logStart + elapsed

                    if (t >= endTimestamp) { isRunning = false; return }

                    const state = {
                        markers: {
                            green1: advance(logs.positions?.green1, positionIndexes, "green1", t),
                            green2: advance(logs.positions?.green2, positionIndexes, "green2", t),
                            blue1: advance(logs.positions?.blue1, positionIndexes, "blue1", t),
                            blue2: advance(logs.positions?.blue2, positionIndexes, "blue2", t),
                        },
                        ball: advance(logs.positions?.ball, positionIndexes, "ball", t),
                        leds: {
                            green1: advance(logs.leds_state?.green1, ledsIndexes, "green1", t),
                            green2: advance(logs.leds_state?.green2, ledsIndexes, "green2", t),
                            blue1: advance(logs.leds_state?.blue1, ledsIndexes, "blue1", t),
                            blue2: advance(logs.leds_state?.blue2, ledsIndexes, "blue2", t),
                        },
                        referee: {
                            wait_ball_position: null,
                        }
                    }

                    renderer.renderFrame(state, markers, {})

                    const referee_state = {
                        game_is_running: advance(logs.referee?.game_is_running, refereeIndexes, "game_is_running", t),
                        game_paused: advance(logs.referee?.game_paused, refereeIndexes, "game_paused", t),
                        timer: advance(logs.referee?.timer, refereeIndexes, "timer", t),
                        game_state_msg: advance(logs.referee?.game_state_msg, refereeIndexes, "game_state_msg", t),
                        teams: advance(logs.referee?.teams, refereeIndexes, "teams", t),
                        referee_history_sliced: advance(logs.referee?.referee_history_sliced, refereeIndexes, "referee_history_sliced", t),
                    }

                    const detection_state = logs.hasOwnProperty("detection_markers") ? {
                        green1: advance(logs.detection_markers?.green1, detectionIndexes, "green1", t),
                        green2: advance(logs.detection_markers?.green2, detectionIndexes, "green2", t),
                        blue1: advance(logs.detection_markers?.blue1, detectionIndexes, "blue1", t),
                        blue2: advance(logs.detection_markers?.blue2, detectionIndexes, "blue2", t),
                        c1: advance(logs.detection_markers?.c1, detectionIndexes, "c1", t),
                        c2: advance(logs.detection_markers?.c2, detectionIndexes, "c2", t),
                        c3: advance(logs.detection_markers?.c3, detectionIndexes, "c3", t),
                        c4: advance(logs.detection_markers?.c4, detectionIndexes, "c4", t),
                    } : null

                    const current_commands = logs.hasOwnProperty("command_received") ? {
                        green1: advance(logs.command_received?.green1, commandsIndexes, "green1", t),
                        green2: advance(logs.command_received?.green2, commandsIndexes, "green2", t),
                        blue1: advance(logs.command_received?.blue1, commandsIndexes, "blue1", t),
                        blue2: advance(logs.command_received?.blue2, commandsIndexes, "blue2", t),
                    } : null

                    if (detection_state !== null) {
                        updateDetection(detection_state)
                    }
                    if (current_commands !== null) {
                        updateCommands(current_commands, t)
                    }
                    updateReferee(referee_state)
                    validationGoal(referee_state.referee_history_sliced, t)

                    currentTimestamp = t
                    frameId = requestAnimationFrame(loop)

                }

                function play() {
                    if (isRunning) return

                    $('.start-replay-grp').addClass('d-none');
                    $('.pause-replay-grp').removeClass('d-none');
                    $('.resume-replay-grp').addClass('d-none');

                    resetUI()

                    if (currentTimestamp == 0) $('.toast').remove()

                    isRunning = true
                    wallStart = performance.now()
                    logStart = currentTimestamp > 0 ? currentTimestamp : startTimestamp
                    frameId = requestAnimationFrame(loop)
                }

                function pause() {
                    $('.pause-replay-grp').addClass('d-none');
                    $('.resume-replay-grp').removeClass('d-none');

                    isRunning = false
                    cancelAnimationFrame(frameId)
                }

                function stop() {
                    $('.start-replay-grp').removeClass('d-none');
                    $('.pause-replay-grp').addClass('d-none');
                    $('.resume-replay-grp').addClass('d-none');

                    isRunning = false
                    cancelAnimationFrame(frameId)
                    currentTimestamp = 0
                    Object.keys(positionIndexes).forEach(k => positionIndexes[k] = 0)
                    Object.keys(ledsIndexes).forEach(k => ledsIndexes[k] = 0)
                    Object.keys(refereeIndexes).forEach(k => refereeIndexes[k] = 0)
                    Object.keys(detectionIndexes).forEach(k => detectionIndexes[k] = 0)
                    Object.keys(commandsIndexes).forEach(k => commandsIndexes[k] = 0)

                    displayed_toast_nb = 0;
                }

                function resetUI() {
                    $("#RefereeHistory").html('');
                    $("#NoHistory").html('<h6 class="text-muted">No History</h6>');
                    displayed_toast_nb = 0;

                    $('.commands-tab .response').html('...')
                    .removeClass("text-bg-danger").removeClass("text-bg-success")

                    $('.commands-tab .age').html('...')
                    .removeClass("text-bg-danger").removeClass("text-bg-warning").removeClass("text-bg-success")

                    $('.commands-tab .command').html('...')

                    $('.detection-tab .detected td').html('...')
                    .removeClass("text-bg-danger").removeClass("text-bg-success")

                    // $('.robot-penalty .detection-value span').html("...").addClass("bg-body-grey")
                }

                function get_display_settings() {
                    let html = ''
                    for (setting_name in display_settings) {
                        let setting = display_settings[setting_name]
                        let checked = setting["value"] ? 'checked="checked"' : ''

                        html += '<div class="form-check form-switch">'
                        html += '    <input class="form-check-input display-setting" type="checkbox"'
                        html += 'role="switch" rel="' + setting_name + '" ' + checked + '>'
                        html += '    <label class="form-check-label" for="flexSwitchCheckDefault">'
                        html += '    ' + setting['label']
                        html += '    </label>'
                        html += '</div>'
                    }

                    $('.display-settings').html(html)
                    $('.display-setting').click(function () {
                        const rel = $(this).attr('rel')
                        const checked = $(this).is(':checked')
                        display_settings[rel]["value"] = checked

                        if (rel === "detection") {
                            if (checked) {
                                $('.detection-view').removeClass('d-none').addClass('d-flex')
                            } else {
                                $('.detection-view').removeClass('d-flex').addClass('d-none')
                            }
                        }
                        else if (rel === "commands") {
                            if (checked) {
                                $('.commands-view').removeClass('d-none').addClass('d-flex')
                            } else {
                                $('.commands-view').removeClass('d-flex').addClass('d-none')
                            }
                        }
                    });
                }

                $('.robot-detection-tab').removeClass('d-flex').addClass('d-none')

                $('.display-python-settings').click(function () {
                    get_display_settings()
                });

                const display_settings = {
                    "detection": { "label": "Show detection view", "default": false },
                    "commands": { "label": "Show commands view", "default": false },
                }
                for (const setting_name in display_settings) {
                    display_settings[setting_name]["value"] = display_settings[setting_name]["default"]
                }

                $('#back').removeClass('d-none')
                $('.sim_vim').css('opacity', '100')
                $('body').addClass('vision-running')

                renderer.drawBg(() => renderer.resizeCanvases())

                $('.start-replay').click(play)
                $('.pause-replay').click(pause)
                $('.stop-replay').click(stop)
            })
        })
        .catch(() => {
            $('.no-file-replay').removeClass('d-none')
        })
}