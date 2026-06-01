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

    fetch("/api/replay_data")
        .then(response => response.json())
        .then(logs => {

            // Check that the logs contain the necessary data
            if (!logs.positions || !logs.referee) {
                throw new Error("Invalid replay file: missing positions or referee")
            }

            backend.constants(function (constants) {
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
                const detectionIndexes = { green1: 0, green2: 0, blue1: 0, blue2: 0, c1: 0, c2: 0, c3: 0, c4: 0 }
                const commandsIndexes = { green1: 0, green2: 0, blue1: 0, blue2: 0 }

                // Calculate start and end timestamps from the unified positions array
                const positionsArray = logs.positions || []
                const startTimestamp = positionsArray.length > 0 ? positionsArray[0].timestamp : 0
                const endTimestamp = positionsArray.length > 0 ? positionsArray[positionsArray.length - 1].timestamp : 0
                
                // Calculate non-running periods once at initialization
                const nonRunningPeriods = (() => {
                    const series = logs.referee?.game_state_msg
                    if (!series?.length) return []
                    
                    const periods = []
                    for (let i = 0; i < series.length; i++) {
                        if (series[i].data !== "Game is running...") {
                            const startTime = series[i].timestamp
                            let endTime = endTimestamp
                            for (let j = i + 1; j < series.length; j++) {
                                if (series[j].data === "Game is running...") {
                                    endTime = series[j].timestamp
                                    break
                                }
                            }
                            periods.push({ start: startTime, end: endTime })
                            while (i < series.length - 1 && series[i + 1].timestamp < endTime) {
                                i++
                            }
                        }
                    }
                    return periods
                })()

                // Setup progress bar with track background
                const totalDuration = endTimestamp - startTimestamp
                $('.replay-progress').css({'position': 'relative', 'background': 'transparent', 'overflow': 'hidden'})
                $('.replay-progress-bar').css({'position': 'absolute', 'z-index': '10', 'top': '0', 'height': '100%'})
                
                // Create background segments showing running vs non-running periods
                const createProgressSegments = () => {
                    // Clear only background segments, keep the progress bar element
                    $('.replay-progress > div:not(.replay-progress-bar)').remove()
                    
                    const series = logs.referee?.game_state_msg
                    if (!series?.length) {
                        // If no game state data, just show a single grey bar
                        $('<div>').css({
                            'position': 'absolute', 'left': '0', 'top': '0', 'width': '100%', 'height': '100%',
                            'background': '#d8d8d8', 'z-index': '1', 'pointer-events': 'none'
                        }).appendTo('.replay-progress')
                        return
                    }
                    
                    // Find the initial state in effect at startTimestamp
                    let initialState = "Not running"  // Default if no data before start
                    for (let i = series.length - 1; i >= 0; i--) {
                        if (series[i].timestamp <= startTimestamp) {
                            initialState = series[i].data
                            break
                        }
                    }
                    
                    let currentTime = startTimestamp
                    let currentState = initialState
                    
                    // Create segments between state changes
                    for (let i = 0; i < series.length; i++) {
                        const stateTime = series[i].timestamp
                        
                        if (stateTime > currentTime && stateTime <= endTimestamp) {
                            // Create segment from currentTime to stateTime using currentState
                            const segmentDuration = stateTime - currentTime
                            const percentage = (segmentDuration / totalDuration) * 100
                            const offsetPercentage = ((currentTime - startTimestamp) / totalDuration) * 100
                            const isRunning = currentState === "Game is running..."
                            const bgColor = isRunning ? '#88aaff' : '#d8d8d8'
                            
                            $('<div>').css({
                                'position': 'absolute', 'left': offsetPercentage + '%', 'top': '0',
                                'width': percentage + '%', 'height': '100%', 'background': bgColor, 'z-index': '1',
                                'pointer-events': 'none'
                            }).appendTo('.replay-progress')
                            
                            currentTime = stateTime
                            currentState = series[i].data
                        }
                    }
                    
                    // Handle final segment from currentTime to end
                    if (currentTime < endTimestamp) {
                        const segmentDuration = endTimestamp - currentTime
                        const percentage = (segmentDuration / totalDuration) * 100
                        const offsetPercentage = ((currentTime - startTimestamp) / totalDuration) * 100
                        const isRunning = currentState === "Game is running..."
                        const bgColor = isRunning ? '#3399ff' : '#d8d8d8'
                        
                        $('<div>').css({
                            'position': 'absolute', 'left': offsetPercentage + '%', 'top': '0',
                            'width': percentage + '%', 'height': '100%', 'background': bgColor, 'z-index': '1',
                            'pointer-events': 'none'
                        }).appendTo('.replay-progress')
                    }
                }
                
                createProgressSegments()

                let isRunning = false
                let frameId = null
                let wallStart = null
                let logStart = startTimestamp
                let currentTimestamp = 0

                let speed = 1

                // Clean up referee_history_sliced
                while(logs.referee?.referee_history_sliced[0]?.data?.length !== 0) {
                    logs.referee.referee_history_sliced.shift()

                    // If we end up with an empty array, break to avoid infinite loop
                    if (logs.referee.referee_history_sliced.length === 0) break;
                }

                $('.replay-progress-grp').removeClass("d-none")

                $('#next-speed').click(function () {
                    speed = 2
                    wallStart = performance.now()
                    logStart = currentTimestamp
                    $(this).addClass("d-none")
                    $(".frame-stepper").prop("disabled", true)

                    $("#reset-spe-forward").removeClass("d-none")
                    $("#prev-speed").removeClass("d-none")
                    $("#reset-spe-back").addClass("d-none")
                    $(".replay-progress-bar").css("background", "#3399ff")
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
                    $(".replay-progress-bar").css("background", "#3399ff")
                    
                })
                $('.reset-speed').click(function () {
                    speed = 1
                    wallStart = performance.now()
                    logStart = currentTimestamp
                    $(this).addClass("d-none")
                    $(".frame-stepper").prop("disabled", false)

                    $("#prev-speed").removeClass("d-none")
                    $("#next-speed").removeClass("d-none")
                    $(".replay-progress-bar").css("background", "#0000ff")
                    
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

                function validationGoal(current_history, t) {

                    let last_index_validation = refereeIndexes.validate_goal
                    let serie_validate_goal = logs.referee?.validate_goal

                    if (!serie_validate_goal?.length) return

                    if (
                        last_index_validation < serie_validate_goal.length &&
                        serie_validate_goal[last_index_validation].timestamp <= t
                    ) {

                        const is_validated = serie_validate_goal[last_index_validation].data

                        const lastEvent = current_history[current_history.length - 1]

                        if (!lastEvent) return

                        const [num] = lastEvent

                        $('#toast-' + num + ' .toast-body').show()

                        if (is_validated) {

                            $("#toast-" + num)
                                .find('.icon')
                                .removeClass('bi-circle-fill')
                                .addClass('bi-check2-circle')

                            $("#toast-" + num)
                                .find('.toast-body')
                                .addClass('text-success')
                                .removeClass('text-danger')
                                .html('<h5 class="m-0">Goal Validated</h5>')

                        } else {

                            $("#toast-" + num)
                                .find('.icon')
                                .removeClass('bi-circle-fill')
                                .addClass('bi-x-circle')

                            $("#toast-" + num)
                                .find('.toast-body')
                                .addClass('text-danger')
                                .removeClass('text-success')
                                .html('<h5 class="m-0">Goal Disallowed</h5>')
                        }

                        refereeIndexes.validate_goal++
                    }
                }


                function updateReferee(referee_state) {
                    if (referee_state.game_state_msg == null) return
                    $('.GameState').html(referee_state.game_state_msg)
                    $('#GreenScore').html(referee_state.teams["green"]["score"])
                    $('#BlueScore').html(referee_state.teams["blue"]["score"])
                    $('.team-name[rel="green"]').val(referee_state.teams["green"]["name"])
                    $('.team-name[rel="blue"]').val(referee_state.teams["blue"]["name"])
                    $('.TimerMinutes').html(formatTimer(referee_state.timer))
                    $('.PlayerName[rel="green"]').val(referee_state.teams["green"]["name"]);
                    $('.PlayerName[rel="blue"]').val(referee_state.teams["blue"]["name"]);

                    updatePenalizedReplayView(referee_state)
                }

                function updateRefereeHistory(history) {

                    for (const history_entry of history) {

                        const [num, time, team, referee_event] = history_entry
                        $("#NoHistory").html('')

                        if (num >= displayed_toast_nb) {

                            let html = ''
                            const vars = {
                                id: num,
                                team,
                                title: referee_event,
                                timestamp: formatTimer(time),
                                event: referee_event
                            }

                            html = team === 'neutral'
                                ? event_neutral_tpl
                                : event_team_tpl

                            for (const key in vars) {
                                html = html.replaceAll('{' + key + '}', vars[key])
                            }

                            $("#RefereeHistory").append(html)
                            $('#toast-' + num + ' .toast-body').hide()
                            $('#toast-' + num).toast('show')
                            $("#tchat").scrollTop($("#tchat")[0].scrollHeight)

                            displayed_toast_nb = num + 1
                        }
                    }
                }

                function updatePenalizedReplayView(referee_state) {
                    for (const [team, team_infos] of Object.entries(referee_state.teams)) {
                        for (const [key, value] of Object.entries(team_infos.robots)) {
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

                    if (t >= endTimestamp || t < startTimestamp) { pause(); return }

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

                    const history = getHistoryUpTo(t)
                    updateRefereeHistory(history)
                    validationGoal(history, t)
                    updateReferee(referee_state)

                    updateProgressBar()

                    currentTimestamp = t
                    renderer.renderFrame(state, markers, {})
                    frameId = requestAnimationFrame(loop)

                }

                function getHistoryUpTo(t) {
                    const series = logs.referee?.referee_history_sliced
                    if (!series?.length) return []

                    const result = []

                    for (const entry of series) {
                        if (entry.timestamp > t) break

                        if (entry.data?.length) {
                            result.push(...entry.data)
                        }
                    }

                    return result
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
                $('#next-game-running').click(function () {
                    const target = getNextGameRunningTime(currentTimestamp)
                    if (target !== null) {
                        seekTo(target)
                    }
                })

                function seekTo(targetTimestamp) {
                    currentTimestamp = targetTimestamp
                    wallStart = performance.now()
                    logStart = targetTimestamp
                    seekIndexes(targetTimestamp)

                    displayed_toast_nb = 0
                    $('.toast').remove()
                    $("#RefereeHistory").html('')
                    $("#NoHistory").html('<h6 class="text-muted">No History</h6>')

                    const {
                        state,
                        referee_state,
                        current_commands,
                    } = buildState(targetTimestamp)

                    renderer.renderFrame(state, markers, {})

                    if (current_commands !== null) {
                        updateCommands(current_commands, targetTimestamp)
                    }

                    const history = getHistoryUpTo(targetTimestamp)
                    updateRefereeHistory(history)

                    updateReferee(referee_state)
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
                    seekSeriesIndexes(detectionIndexes, key => logs.detection_markers?.[key], t)
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
                    $('.replay-btn').prop('disabled', true)

                    isRunning = false
                    cancelAnimationFrame(frameId)
                    currentTimestamp = 0
                    positionIndex = 0
                    Object.keys(ledsIndexes).forEach(k => ledsIndexes[k] = 0)
                    Object.keys(refereeIndexes).forEach(k => refereeIndexes[k] = 0)
                    Object.keys(detectionIndexes).forEach(k => detectionIndexes[k] = 0)
                    Object.keys(commandsIndexes).forEach(k => commandsIndexes[k] = 0)

                    updateProgressBar()

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
                }

                function isCurrentlyInNonRunningPeriod(t) {
                    const series = logs.referee?.game_state_msg
                    if (!series?.length) return false
                    
                    // Find the most recent entry at or before time t
                    let lastEntry = null
                    for (let i = series.length - 1; i >= 0; i--) {
                        if (series[i].timestamp <= t) {
                            lastEntry = series[i]
                            break
                        }
                    }
                    
                    return lastEntry && lastEntry.data !== "Game is running..."
                }

                function getNextGameRunningTime(fromTime) {
                    const series = logs.referee?.game_state_msg
                    if (!series?.length) return null
                    
                    for (const entry of series) {
                        if (entry.timestamp > fromTime && entry.data === "Game is running...") {
                            return entry.timestamp
                        }
                    }
                    return null
                }

                function updateProgressBar() {
                    const progress = (currentTimestamp - startTimestamp) / (endTimestamp - startTimestamp) * 100
                    $('.replay-progress-bar').css('width', progress + '%')
                    
                    // Show/hide next game running button
                    const inNonRunning = isCurrentlyInNonRunningPeriod(currentTimestamp)
                    const hasNextRunning = getNextGameRunningTime(currentTimestamp) !== null
                    
                    if (inNonRunning && hasNextRunning) {
                        $('#next-game-running').removeClass('d-none').prop('disabled', false)
                    } else {
                        $('#next-game-running').addClass('d-none').prop('disabled', true)
                    }
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

                        if (rel === "penalized-tab") {
                            if (checked) {
                                $('.penalized-replay-view').removeClass('d-none').addClass('d-flex')
                            } else {
                                $('.penalized-replay-view').removeClass('d-flex').addClass('d-none')
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
                    "commands": { "label": "Show commands view", "default": false },
                    "penalized-tab": { "label": "Show penalized robots", "default": true },
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
            $('.penalized-replay-view').addClass('d-none')
        })
}