// Simulated view of the field (drawn from the state): used in simulation, and as an alternative to
// the camera image in real mode. In simulation, robots and ball can be moved with the mouse.

function simulator_initialize(backend, constants, isSimulated) {
    const renderer = createFieldRenderer(constants);

    let markers = {};
    for (let marker of ['blue1', 'blue2', 'green1', 'green2']) {
        markers[marker] = { image: new Image(), pos: [0, 0, 0], leds: [0, 0, 0] };
        markers[marker].image.src = 'static/imgs/robot' + marker + '.png';
    }

    // Display settings of the simulated view (in real mode, the display settings are the vision
    // ones, see video.js)
    let displaySettings = {
        landmark: { label: 'Center landmark', default: true },
        timed_circle: { label: 'Timed circle (around the ball)', default: false },
    };
    for (let name in displaySettings) {
        displaySettings[name].value = displaySettings[name].default;
    }

    if (isSimulated) {
        let html = '';
        for (let name in displaySettings) {
            html += '<div class="form-check form-switch">'
                + '<input class="form-check-input sim-display-setting" type="checkbox" role="switch" id="sim-display-' + name + '" rel="' + name + '"'
                + (displaySettings[name].value ? ' checked' : '') + '>'
                + '<label class="form-check-label" for="sim-display-' + name + '">' + displaySettings[name].label + '</label>'
                + '</div>';
        }
        $('.display-settings').html(html);
        $('.sim-display-setting').change(function () {
            displaySettings[$(this).attr('rel')].value = $(this).is(':checked');
        });
    }

    // Simulated view on/off
    let simView = false;
    let backgroundReady = false;

    function setSimView(enabled) {
        simView = enabled;
        $('body').toggleClass('sim-view', enabled);
        $('.view-change-label').text(enabled ? 'Camera view' : 'Simulated view');
        if (enabled && !backgroundReady) {
            renderer.drawBg(function () {
                backgroundReady = true;
                renderer.resizeCanvases();
            });
        } else if (enabled) {
            renderer.resizeCanvases();
        }
    }

    setSimView(isSimulated);
    $('.view-change').click(function () {
        setSimView(!simView);
    });

    $(window).on('resize', function () {
        if (simView) {
            renderer.resizeCanvases();
        }
    });
    $(document).on('rsk:tab', function (event, tab) {
        if (tab == 'referee' && simView) {
            // The canvases had no size while hidden
            setTimeout(renderer.resizeCanvases, 0);
        }
    });

    // Rendering loop (only when visible)
    let frames = 0;
    let fpsStart = Date.now();

    function update() {
        if (!simView || current_tab != 'referee' || !backgroundReady || document.hidden) {
            return;
        }
        backend.get_state(function (state) {
            renderer.renderFrame(state, markers, displaySettings);

            if (isSimulated) {
                frames += 1;
                let elapsed = Date.now() - fpsStart;
                if (elapsed > 1000) {
                    $('.fps').text('FPS: ' + Math.round(1000 * frames / elapsed));
                    frames = 0;
                    fpsStart = Date.now();
                }
            }
        });
    }
    setInterval(update, 1000 / 30);

    // Moving the robots and the ball with the mouse (simulation only): left button moves, right
    // button rotates
    if (isSimulated) {
        const canvas = document.getElementById('ball');
        $(canvas).addClass('interactive');

        let selected = null;
        let dragType = null;
        let start = null;

        function teleport(event) {
            let x = event.offsetX, y = event.offsetY;
            let target = selected == 'ball' ? [0, 0, 0] : markers[selected].pos;
            let world = renderer.screenToWorld(dragType == 'position' ? x : target[0], dragType == 'position' ? y : target[1]);
            let orientation = 0;
            if (selected != 'ball') {
                orientation = dragType == 'position'
                    ? -(target[2] - Math.PI / 2)
                    : -Math.atan2(y - target[1], x - target[0]);
            }
            backend.teleport(selected, world[0], world[1], orientation);
        }

        canvas.addEventListener('contextmenu', function (event) {
            event.preventDefault();
        });

        canvas.addEventListener('mousedown', function (event) {
            selected = 'ball';
            let radius = constants.robot_radius * renderer.getRatioW();
            for (let marker in markers) {
                let pos = markers[marker].pos;
                if (Math.hypot(pos[0] - event.offsetX, pos[1] - event.offsetY) < radius) {
                    selected = marker;
                }
            }
            dragType = event.button == 0 ? 'position' : 'orientation';
            if (selected == 'ball' && dragType == 'orientation') {
                selected = null;
                return;
            }
            start = [event.offsetX, event.offsetY];
            canvas.style.cursor = 'grabbing';
            teleport(event);
        });

        canvas.addEventListener('mousemove', function (event) {
            if (selected) {
                teleport(event);
            }
        });

        function release(event) {
            if (selected) {
                teleport(event);
            }
            selected = null;
            canvas.style.cursor = '';
        }
        canvas.addEventListener('mouseup', release);
        canvas.addEventListener('mouseleave', function () {
            selected = null;
            canvas.style.cursor = '';
        });
    }
}
