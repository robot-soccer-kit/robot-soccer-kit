// Replay mode: plays a recorded game (positions, referee, commands)

function replay_initialize(backend, constants) {
    const view = createRefereeView(constants)

    $('.team-name').prop('disabled', true)

    fetch("/api/replay_data")
        .then(response => response.json())
        .then(logs => {

            // Check that the logs contain the necessary data
            if (!logs.positions || !logs.referee) {
                throw new Error("Invalid replay file: missing positions or referee")
            }

            {
                const renderer = createFieldRenderer(constants)
                $(window).on("resize", renderer.resizeCanvases)


                const markers = {}
                for (const key of ["blue1", "blue2", "green1", "green2"]) {
                    markers[key] = { image: new Image(), pos: [0, 0, 0], leds: [0, 0, 0] }
                    markers[key].image.src = "static/imgs/robot" + key + ".png"
                }

                let positionIndex = 0
                
                // Cache of last known positions for robots (for rendering stale positions)
                const lastKnownPositions = {
                    green1: null,
                    green2: null,
                    blue1: null,
                    blue2: null
                }
                
                const ledsIndexes = { green1: 0, green2: 0, blue1: 0, blue2: 0 }
                const refereeIndexes = { game_is_running: 0, game_paused: 0, timer: 0, game_state_msg: 0, teams: 0, validate_goal: 0 }
                const commandsIndexes = { green1: 0, green2: 0, blue1: 0, blue2: 0 }

                // Calculate start and end timestamps from the unified positions array
                const positionsArray = logs.positions || []
                const startTimestamp = positionsArray.length > 0 ? positionsArray[0].timestamp : 0
                const endTimestamp = positionsArray.length > 0 ? positionsArray[positionsArray.length - 1].timestamp : 0

                let isRunning = false
                let frameId = null
                let wallStart = null
                let logStart = startTimestamp
                let currentTimestamp = 0

                let speed = 1

                // The beginning of the record can contain the history of the previous game (recorded
                // before this game was started, which empties the history): it is skipped
                const sliced = logs.referee?.referee_history_sliced
                if (Array.isArray(sliced)) {
                    const start = sliced.findIndex(entry => entry?.data?.length === 0)
                    if (start > 0) {
                        sliced.splice(0, start)
                    }
                }

                $('#next-speed').click(function () {
                    speed = 2
                    wallStart = performance.now()
                    logStart = currentTimestamp
                    $(this).addClass("d-none")
                    $(".frame-stepper").prop("disabled", true)

                    $("#reset-spe-forward").removeClass("d-none")
                    $("#prev-speed").removeClass("d-none")
                    $("#reset-spe-back").addClass("d-none")
                    $(".replay-progress").addClass("fast")
                })
                $('#prev-speed').click(function () {
                    speed = -2
                    wallStart = performance.now()
                    logStart = currentTimestamp
                    $(this).addClass("d-none")
                    $(".frame-stepper").prop("disabled", true)

                    $("#reset-spe-back").removeClass("d-none")
                    $("#next-speed").removeClass("d-none")
                    $("#reset-spe-forward").addClass("d-none")
                    $(".replay-progress").addClass("fast")
                    
                })
                $('.reset-speed').click(function () {
                    speed = 1
                    wallStart = performance.now()
                    logStart = currentTimestamp
                    $(this).addClass("d-none")
                    $(".frame-stepper").prop("disabled", false)

                    $("#prev-speed").removeClass("d-none")
                    $("#next-speed").removeClass("d-none")
                    $(".replay-progress").removeClass("fast")
                    
                })

                function buildState(t) {
                    // Find the position frame at or before time t
                    let frameMarkers = {}
                    let frameBall = null
                    
                    // Search for the frame at time t
                    while (positionIndex + 1 < positionsArray.length && 
                           positionsArray[positionIndex + 1].timestamp <= t) {
                        positionIndex++
                    }
                    
                    // If we're at a valid frame and it's before/at time t, use its data
                    if (positionIndex < positionsArray.length && 
                        positionsArray[positionIndex].timestamp <= t) {
                        const frame = positionsArray[positionIndex]
                        frameMarkers = frame.markers || {}
                        frameBall = frame.ball ?? null
                        
                        // Update last known positions for detected markers
                        for (const [key, data] of Object.entries(frameMarkers)) {
                            lastKnownPositions[key] = {
                                position: data.position,
                                orientation: data.orientation,
                                timestamp: frame.timestamp
                            }
                        }
                    }
                    
                    // Build state with detected markers and their cache status
                    const stateMarkers = {}
                    for (const robotKey of ["green1", "green2", "blue1", "blue2"]) {
                        if (frameMarkers[robotKey]) {
                            // Robot detected in current frame
                            stateMarkers[robotKey] = frameMarkers[robotKey]
                        } else if (lastKnownPositions[robotKey]) {
                            // Robot not detected in current frame, use cache
                            stateMarkers[robotKey] = {
                                position: lastKnownPositions[robotKey].position,
                                orientation: lastKnownPositions[robotKey].orientation,
                                _is_stale: true  // Mark as stale for rendering
                            }
                        }
                    }

                    const state = {
                        markers: stateMarkers,
                        ball: frameBall,

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

                    const referee_state = {
                        game_is_running: advance(logs.referee?.game_is_running, refereeIndexes, "game_is_running", t),
                        game_paused: advance(logs.referee?.game_paused, refereeIndexes, "game_paused", t),
                        timer: advance(logs.referee?.timer, refereeIndexes, "timer", t),
                        game_state_msg: advance(logs.referee?.game_state_msg, refereeIndexes, "game_state_msg", t),
                        teams: advance(logs.referee?.teams, refereeIndexes, "teams", t),
                    }

                    const current_commands = logs.hasOwnProperty("command_received")
                        ? {
                            green1: advance(logs.command_received?.green1, commandsIndexes, "green1", t),
                            green2: advance(logs.command_received?.green2, commandsIndexes, "green2", t),
                            blue1: advance(logs.command_received?.blue1, commandsIndexes, "blue1", t),
                            blue2: advance(logs.command_received?.blue2, commandsIndexes, "blue2", t),
                        }
                        : null

                    return {
                        state,
                        referee_state,
                        current_commands,
                    }
                }

                function advance(series, indexes, key, t) {
                    if (!series?.length) return null
                    while (indexes[key] + 1 < series.length && series[indexes[key] + 1].timestamp <= t) {
                        indexes[key]++
                    }
                    return series[indexes[key]]?.timestamp <= t ? series[indexes[key]].data : null
                }

                // Referee history up to t: entries with the time they appeared
                function getHistoryEntries(t) {
                    const series = logs.referee?.referee_history_sliced
                    if (!series?.length) return []

                    const entries = {}
                    for (const entry of series) {
                        if (entry.timestamp > t) break
                        for (const event of entry.data || []) {
                            if (!(event[0] in entries)) {
                                entries[event[0]] = { event, timestamp: entry.timestamp }
                            }
                        }
                    }
                    return Object.values(entries).sort((a, b) => a.event[0] - b.event[0])
                }

                // Old records don't have the goal decisions in the history: they are retrieved
                // from the validate_goal series (a decision concerns the last goal before it)
                function getGoalOutcomes(entries, t) {
                    const outcomes = {}
                    for (const decision of logs.referee?.validate_goal || []) {
                        if (decision.timestamp > t) break
                        const goal = [...entries].reverse().find(
                            entry => entry.event[3] == 'Goal' && entry.timestamp <= decision.timestamp)
                        if (goal) outcomes[goal.event[0]] = decision.data
                    }
                    return outcomes
                }

                let teamNames = {}

                function updateRefereeHistory(t, scrollToEnd = false) {
                    const entries = getHistoryEntries(t)
                    view.renderHistory(entries.map(entry => entry.event), {
                        outcomes: getGoalOutcomes(entries, t),
                        scrollToEnd: scrollToEnd,
                        teamNames: teamNames,
                    })
                }

                function updateReferee(referee_state) {
                    if (referee_state.teams) {
                        teamNames = { green: referee_state.teams.green.name, blue: referee_state.teams.blue.name }
                        view.render(referee_state, { live: false })
                    } else {
                        $('.GameState').text(referee_state.game_state_msg || '')
                        $('.TimerMinutes').text(formatTimer(referee_state.timer))
                    }
                    updatePenalizedReplayView(referee_state)
                }

                function updatePenalizedReplayView(referee_state) {
                    for (const [team, team_infos] of Object.entries(referee_state.teams || {})) {
                        for (const [key, value] of Object.entries(team_infos.robots || {})) {
                            if(value?.penalized) {
                                $('.penalized-replay td[rel="' + team + key + '"]').html("true").addClass("text-bg-danger").removeClass("text-bg-success");
                                $('.remaining-time-replay td[rel="' + team + key + '"]').html(value.penalized_remaining).addClass("text-bg-warning");
                                $('.penalized-reason-replay td[rel="' + team + key + '"]').html(value.penalized_reason).addClass("text-bg-warning");
                            } else {
                                $('.penalized-replay td[rel="' + team + key + '"]').html("false").removeClass("text-bg-danger").addClass("text-bg-success");
                                $('.remaining-time-replay td[rel="' + team + key + '"]').html('...').removeClass("text-bg-warning");
                                $('.penalized-reason-replay td[rel="' + team + key + '"]').html('...').removeClass("text-bg-warning");
                            }
                            
                        }
                    }
                }

                function updateCommands(current_commands, t) {
                    for (const [key, value] of Object.entries(current_commands)) {
                        if (!value) continue
                        let [command_name, ...args] = value["received"]
                        let response = value["response"] // ex [true, "ok"]
                        let is_master = value["master"]

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
                    const elapsed = (performance.now() - wallStart) / 1000 * speed
                    const t = logStart + elapsed

                    if (t >= endTimestamp) { pause(); return }

                    if (t < currentTimestamp) {
                        seekIndexes(t)
                    }

                    const {
                        state,
                        referee_state,
                        current_commands,
                    } = buildState(t)

                    if (current_commands !== null) {
                        updateCommands(current_commands, t)
                    }

                    updateReferee(referee_state)
                    updateRefereeHistory(t)

                    updateProgressBar()

                    currentTimestamp = t
                    renderer.renderFrame(state, markers, {})
                    frameId = requestAnimationFrame(loop)

                }

                function getNextPositionTimestamp(t, direction = 1) {
                if (direction > 0) {
                    for (let i = positionIndex + 1; i < positionsArray.length; i++) {
                        if (positionsArray[i].timestamp > t) return positionsArray[i].timestamp
                    }
                    return endTimestamp
                } else {
                    for (let i = positionIndex - 1; i >= 0; i--) {
                        if (positionsArray[i].timestamp < t) return positionsArray[i].timestamp
                    }
                    return startTimestamp
                }
            }

                $('#next-frame').click(function () {
                    const target = getNextPositionTimestamp(currentTimestamp, 1)
                    seekTo(target)
                })
                $('#prev-frame').click(function () {
                    const target = getNextPositionTimestamp(currentTimestamp, -1)
                    seekTo(target)
                })

                function seekTo(targetTimestamp) {
                    currentTimestamp = targetTimestamp
                    wallStart = performance.now()
                    logStart = targetTimestamp
                    seekIndexes(targetTimestamp)

                    const {
                        state,
                        referee_state,
                        current_commands,
                    } = buildState(targetTimestamp)

                    renderer.renderFrame(state, markers, {})

                    if (current_commands !== null) {
                        updateCommands(current_commands, targetTimestamp)
                    }

                    updateReferee(referee_state)
                    updateRefereeHistory(targetTimestamp, true)
                    updateProgressBar()
                }

                function seekSeriesIndexes(indexes, getter, t) {

                    for (const key of Object.keys(indexes)) {

                        indexes[key] = 0

                        const series = getter(key)

                        if (!series?.length) continue

                        while (indexes[key] + 1 < series.length && series[indexes[key] + 1].timestamp <= t) {
                            indexes[key]++
                        }
                    }
                }

                function seekIndexes(t) {
                    // Seek position index in the unified positions array
                    positionIndex = 0
                    while (positionIndex + 1 < positionsArray.length && 
                           positionsArray[positionIndex + 1].timestamp <= t) {
                        positionIndex++
                    }
                    
                    // Seek other indexes as before
                    seekSeriesIndexes(ledsIndexes, key => logs.leds_state?.[key], t)
                    seekSeriesIndexes(refereeIndexes, key => logs.referee?.[key], t)
                    seekSeriesIndexes(commandsIndexes, key => logs.command_received?.[key], t)

                    refereeIndexes.validate_goal = 0
                    const serieValidation = logs.referee?.validate_goal
                    if (serieValidation?.length) {
                        while (refereeIndexes.validate_goal + 1 < serieValidation.length && 
                            serieValidation[refereeIndexes.validate_goal + 1].timestamp <= t) {
                            refereeIndexes.validate_goal++
                        }
                    }
                }

                function play() {
                    if (isRunning) return

                    $('.start-replay-grp').addClass('d-none');
                    $('.pause-replay-grp').removeClass('d-none');
                    $('.resume-replay-grp').addClass('d-none');
                    $('.replay-btn').prop('disabled', false)

                    resetUI()

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
                    $('.replay-btn').prop('disabled', true)

                    isRunning = false
                    cancelAnimationFrame(frameId)
                    currentTimestamp = 0
                    positionIndex = 0
                    Object.keys(ledsIndexes).forEach(k => ledsIndexes[k] = 0)
                    Object.keys(refereeIndexes).forEach(k => refereeIndexes[k] = 0)
                    Object.keys(commandsIndexes).forEach(k => commandsIndexes[k] = 0)

                    updateProgressBar()
                    updateRefereeHistory(-Infinity)
                }

                function resetUI() {
                    $('.commands-tab .response').html('...')
                        .removeClass("text-bg-danger").removeClass("text-bg-success")

                    $('.commands-tab .age').html('...')
                        .removeClass("text-bg-danger").removeClass("text-bg-warning").removeClass("text-bg-success")

                    $('.commands-tab .command').html('...')

                }

                function updateProgressBar() {
                    const progress = (currentTimestamp - startTimestamp) / (endTimestamp - startTimestamp) * 100
                    $('.replay-progress-bar').css('width', progress + '%')
                }
  
                $('.replay-progress').click(function (e) {
                    if (currentTimestamp !== 0 || isRunning) {
                        const ratio = e.offsetX / $(this).width()
                        const targetTimestamp = startTimestamp + ratio * (endTimestamp - startTimestamp)
                        seekTo(targetTimestamp)
                    }
                })

                function get_display_settings() {
                    let html = ''
                    for (const setting_name in display_settings) {
                        const setting = display_settings[setting_name]
                        html += '<div class="form-check form-switch">'
                            + '<input class="form-check-input display-setting" type="checkbox" role="switch" id="replay-display-' + setting_name + '" rel="' + setting_name + '"'
                            + (setting.value ? ' checked' : '') + '>'
                            + '<label class="form-check-label" for="replay-display-' + setting_name + '">' + setting.label + '</label>'
                            + '</div>'
                    }
                    $('.display-settings').html(html)
                }

                $('.display-settings').on('change', '.display-setting', function () {
                    const rel = $(this).attr('rel')
                    display_settings[rel].value = $(this).is(':checked')
                    if (rel === "penalized-tab") {
                        $('.penalized-replay-view').toggleClass('d-none', !display_settings[rel].value)
                    } else if (rel === "commands") {
                        $('.commands-view').toggleClass('d-none', !display_settings[rel].value)
                    }
                })

                $('#settings-panel').on('show.bs.offcanvas', get_display_settings)

                const display_settings = {
                    "commands": { "label": "Show commands view", "default": false },
                    "penalized-tab": { "label": "Show penalized robots", "default": true },
                }
                for (const setting_name in display_settings) {
                    display_settings[setting_name]["value"] = display_settings[setting_name]["default"]
                }

                $('body').addClass('sim-view')

                renderer.drawBg(() => renderer.resizeCanvases())

                $('.start-replay').click(play)
                $('.pause-replay').click(pause)
                $('.stop-replay').click(stop)
            }
        })
        .catch(() => {
            $('.no-file-replay').removeClass('d-none')
            $('.penalized-replay-view').addClass('d-none')
        })
}