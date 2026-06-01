function simulator_initialize(backend, isView) {
    backend.constants(function (constants) {
        const renderer = createFieldRenderer(constants)

        $(window).on("resize", renderer.updateRatios)

        function isDifferent(lastPos, position) {
            minimumTranslation = 1
            minimumRotation = 0.05
            if (Math.abs(lastPos[0] - position[0]) > minimumTranslation) {
                return true
            } else if (Math.abs(lastPos[1] - position[1]) > minimumTranslation) {
                return true
            } else if (Math.abs(lastPos[2] - position[2]) > minimumRotation) {
                return true
            }
            return false
        }

        function UpdateView() {

            // FPS Limit
            backend.get_state(function (state) {
                if (state.simulated) {
                    tick += 1
                    if (Date.now() - T0 > 100) {
                        $('.fps').text("FPS : " + Math.round(1000 / ((Date.now() - T0) / tick)));
                        T0 = Date.now()
                        tick = 0
                    }
                }
                renderer.renderFrame(state, markers, display_settings)
            });
        }

        function runView() {
            $('#ViewChange').html("<i class='bi bi-camera'></i> Camera View")
            $('#vision').addClass('d-none')
            $('#back').removeClass('d-none')
            $('.sim_vim').css('opacity', '100')

            renderer.drawBg()

            markers = { "blue1": NaN, "blue2": NaN, "green1": NaN, "green2": NaN }
            for (let marker in markers) {
                markers[marker] = { "image": NaN, "context": NaN, "pos": [0, 0, 0], "leds": [0, 0, 0], "clear": true }
            }
            for (var key in markers) {
                markers[key]["image"] = new Image();
                markers[key]["image"].src = "static/imgs/robot" + key + ".png"
            }
            
            renderer.resizeCanvases()

            clearInterval(intervalId)
            intervalId = setInterval(UpdateView, 1000 / fps_limit)
        }

        function clearView() {
            clearInterval(intervalId)
            intervalId = NaN
            $('#ViewChange').html("<i class='bi bi-camera'></i> Simulated View")
            $('#vision').removeClass('d-none')
            $('#back').addClass('d-none')
            $('.sim_vim').css('opacity', '0')
        }

        function switchView() {
            if (isNaN(intervalId)) {
                runView()
            } else {
                clearView()
            }
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
            html += '<div class="range">'
            html += '<label class="form-label" for="flexSwitchCheckDefault">FPS Limit : ' + fps_limit + '</label>'
            html += '<input id="aaaa" type="range" class="form-range" min="10" max="65" step="5" value="' + fps_limit + '", >'
            html += '</div>'

            $('.display-settings').html(html)
            $('.display-setting').click(function () {
                display_settings[$(this).attr('rel')]["value"] = $(this).is(':checked')
            });

            // //give the backend the state of the recording settings
            // backend.set_ready_to_record($('.enable-rec-settings input').is(':checked'))

            document.querySelector(".range .form-range").addEventListener('input', function (aa) {
                fps_limit = this.value
                clearInterval(intervalId)
                if (fps_limit == 65) {
                    intervalId = setInterval(UpdateView, 1000 / 240)
                    $('.form-label').text("FPS Limit : unlimited")
                } else {
                    intervalId = setInterval(UpdateView, 1000 / fps_limit)
                    $('.form-label').text("FPS Limit : " + fps_limit)
                }
            })

        }
        $('.display-python-settings').click(function () {
            get_display_settings()
        });

        display_settings = {
            "landmark": { "label": "Center Landmark", "default": true, "type": "" },
            "timed_circle": { "label": "Timed Circle", "default": false, "type": "" },
        }
        for (setting_name in display_settings) {
            display_settings[setting_name]["value"] = display_settings[setting_name]["default"]
        }

        $('.show-rec-settings').click(function () {
            $('.show-rec-settings').removeClass("btn-outline-secondary").addClass("btn-secondary")
            $('.show-general-settings').removeClass("btn-secondary").addClass("btn-outline-secondary")
            $('.general-settings').css("display", "none")
            $('.recording-settings').show()
        })

        $('.show-general-settings').click(function () {
            $('.show-general-settings').removeClass("btn-outline-secondary").addClass("btn-secondary")
            $('.show-rec-settings').removeClass("btn-secondary").addClass("btn-outline-secondary")
            $('.recording-settings').css("display", "none")
            $('.general-settings').show()
        })

        const carpetSize = [constants["carpet_length"], constants["carpet_width"]]
        intervalId = NaN
        let fps_limit = 30
        let selectedObjet = "ball"
        let tick = 0
        let T0 = Date.now()

        if (isView) {
            setTimeout(runView, 1000)
            runView()
        }
        // else {
        //     clearView()
        // }

        $('#ViewChange').click(switchView)

        backend.is_simulated(function (isSimulated) {
            if (isView) window.onresize = runView
            
            if (isSimulated) {
                $('body').addClass('vision-running')
                const canvas = document.getElementById("ball")
                const distance = (x1, y1, x2, y2) => Math.hypot(x2 - x1, y2 - y1);
                let dragType = null
                let initialPosition = null

                function teleportSelectedObjectOnMouse(e) {
                    let reelPos = [0.0, 0.0, 0.0]
                    pos = [...initialPosition]

                    if (dragType == "position") {
                        pos[0] = e.layerX
                        pos[1] = e.layerY
                    } else {
                        pos[2] = Math.atan2(e.layerY - initialPosition[1], e.layerX - initialPosition[0]) + Math.PI / 2
                    }

                    const worldPos = renderer.screenToWorld(pos[0], pos[1])
                    reelPos[0] = worldPos[0]
                    reelPos[1] = worldPos[1]
                    reelPos[2] = -(pos[2] - Math.PI / 2)
                    backend.teleport(selectedObjet, reelPos[0], reelPos[1], reelPos[2])
                }
                canvas.addEventListener("mousedown", function (e) {
                    for (let marker in markers) {
                        if (distance(markers[marker]["pos"][0], markers[marker]["pos"][1], e.layerX, e.layerY) < constants["robot_radius"] * renderer.getRatioW()) {
                            selectedObjet = marker
                        }
                    }
                    dragType = (e.button == 0) ? "position" : "orientation"
                    if (selectedObjet != "ball") {
                        initialPosition = markers[selectedObjet]["pos"]
                    } else {
                        initialPosition = [0., 0., 0.]
                    }

                    canvas.addEventListener("mousemove", teleportSelectedObjectOnMouse)
                })
                canvas.addEventListener("mouseup", function (e) {
                    teleportSelectedObjectOnMouse(e)
                    canvas.removeEventListener("mousemove", teleportSelectedObjectOnMouse)
                    selectedObjet = "ball"
                })
            }
        })


    })
}