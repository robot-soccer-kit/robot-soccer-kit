// Drawing of the simulated view of the field (Referee tab): the robots, their LEDs, the ball,
// the ball placement circle and the display settings (center landmark, timed circle), on the
// canvases #back (field image), #robots and #ball

function createFieldRenderer(constants) {
    let ratio_w, ratio_h, back_width, back_height

    function updateRatios() {
        const back = document.getElementById('back')
        back_width  = back.offsetWidth
        back_height = back.offsetHeight
        ratio_w = back_width  / constants.carpet_length
        ratio_h = Math.min(back_width / constants.carpet_length,
                           back_height / constants.carpet_width)
    }

    function transformViewToSim(position, orientation = 0) {
        return [
            position[0] * ratio_w + back_width  / 2,
           -position[1] * ratio_h + back_height / 2,
            round(-(orientation) + Math.PI / 2)
        ]
    }

    function drawCircle(position, radius, color, canvas, clear = false, tickness = 0, dash = 0) {
        const context = canvas.getContext('2d')
        if (clear) context.clearRect(0, 0, canvas.width, canvas.height)
        context.beginPath()
        context.strokeStyle = color
        context.fillStyle = color
        if (dash != 0) context.setLineDash(dash);
        else context.setLineDash([]);
        context.arc(position[0], position[1], radius, 0, Math.PI * 2);
        context.lineWidth = tickness
        if (tickness == 0) context.fill()
        else context.stroke()
    }

    function drawline(begin, end, canvas, color, tickness = 0) {
        const context = canvas.getContext('2d')
        context.beginPath()
        context.strokeStyle = color
        context.fillStyle = color

        context.moveTo(...begin);
        context.lineTo(...end);
        context.lineWidth = tickness
        context.stroke()
    }
    function drawLeds(color, context) {
        for (let i = -30; i < -30 + 120 * 3; i += 120) {
            const angle = i * Math.PI / 180
            const x = Math.round(Math.cos(angle) * constants["robot_radius"] * ratio_w * 0.93)
            const y = Math.round(Math.sin(angle) * constants["robot_radius"] * ratio_w * 0.93)
            context.beginPath()
            const gradient = context.createRadialGradient(x, y, 0, x, y, 70);
            gradient.addColorStop(0.05, "rgba(" + color + ",1)");
            gradient.addColorStop(0.1, "rgba(" + color + ",0.5)");
            gradient.addColorStop(0.25, "rgba(" + color + ",0)");
            context.fillStyle = gradient
            context.fillRect(x - 25, y - 25, 200, 200);
        }
    }

    function drawBall(position) {
        const ball = transformViewToSim(position)
        const ballCanvas = document.getElementById("ball")
        const ballRadius = constants["ball_radius"] * ratio_w
        drawCircle(ball, ballRadius, "orange", ballCanvas, true)
    }

    function renderFrame(state, markers, displaySettings = {}) {
        let canvas = document.getElementById("robots")

        // The canvases have no size while they are hidden (e.g. other tab)
        if (!canvas.width || !canvas.height || !ratio_w) {
            resizeCanvases()
            if (!canvas.width || !canvas.height) {
                return
            }
        }

        let presentMarker = state.markers

        if (!("offscreenCanvas" in canvas)) {
            canvas.offscreenCanvas = document.createElement("canvas")
        }
        canvas.offscreenCanvas.width = canvas.width
        canvas.offscreenCanvas.height = canvas.height

        let context = canvas.offscreenCanvas.getContext("2d")
        context.resetTransform()
        context.clearRect(0, 0, canvas.width, canvas.height)

        // Draw present Robot
        for (var entry in presentMarker) {
            const robot = presentMarker[entry]
            if (!robot) continue
            const robotPos = transformViewToSim(robot.position, robot.orientation)

            // Context placement
            context.resetTransform()
            context.translate(robotPos[0], robotPos[1])
            context.rotate(robotPos[2])

            // Draw leds
            if (Object.keys(state["leds"]).length != 0 && state["leds"][entry]?.length == 3) {
                markers[entry]["leds"] = [...state["leds"][entry]]
                for (var i = 0; i < 3; i++) {
                    markers[entry]["leds"][i] = Math.round(Math.min(255, 50 + Math.log(markers[entry]["leds"][i] + 1) / Math.log(256) * 255))
                }
                drawLeds(markers[entry]["leds"], context)
            }

            let robotSize = constants["robot_radius"] * 2 * ratio_w
            context.imageSmoothingEnabled = true
            context.drawImage(markers[entry]["image"], -robotSize / 2, -robotSize / 2, robotSize, robotSize)
            
            // If robot is stale (not detected in current frame), draw a red X
            if (robot._is_stale) {
                context.strokeStyle = "red"
                context.lineWidth = 3
                context.globalAlpha = 0.7
                const crossSize = robotSize / 3
                context.beginPath()
                context.moveTo(-crossSize, -crossSize)
                context.lineTo(crossSize, crossSize)
                context.stroke()
                context.beginPath()
                context.moveTo(crossSize, -crossSize)
                context.lineTo(-crossSize, crossSize)
                context.stroke()
                context.globalAlpha = 1.0
            }
            
            markers[entry]["pos"] = robotPos
            markers[entry]["clear"] = false
        }

        canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height)
        canvas.getContext("2d").drawImage(canvas.offscreenCanvas, 0, 0)

        //Draw Ball and placement circle 
        const ballCanvas = document.getElementById("ball")

        if (state.ball != null) {
            drawBall(state.ball)
        }

        const placementCirclePosition = state.referee?.wait_ball_position ?? null
        if (placementCirclePosition != null) {
            drawCircle(transformViewToSim(placementCirclePosition), constants.place_ball_margin * ratio_w, "red", ballCanvas, false, 1)
        }

        if (displaySettings["landmark"]?.["value"]) {
            const center = [ballCanvas.width / 2, ballCanvas.height / 2]
            drawline(center, [center[0], center[1] - 100], ballCanvas, "green")
            drawline(center, [center[0] + 100, center[1]], ballCanvas, "red")
        }

        if (displaySettings["timed_circle"]?.["value"] && state.ball) {
            drawCircle(transformViewToSim(state.ball), constants.timed_circle_radius * ratio_w, "red", ballCanvas, false, 1, [10, 10])
        }
    }

    // The field image is as large as possible in its area, keeping its ratio
    // Keep in sync with the phones media query of app.css
    const PHONE_FIT = '(max-width: 767.98px) and (min-height: 480px)'

    function fitBackground() {
        const back = document.getElementById('back')
        const view = back.closest('.field-view')
        if (!view || !back.width || !back.height) return
        const ratio = back.width / back.height
        let fitWidth
        // Phones in portrait (referee tab): the field fits the remaining room (see app.css)
        const phoneFit = window.matchMedia(PHONE_FIT).matches
            && document.body.dataset.tab == 'referee'
            && !document.body.classList.contains('mode-replay')
        if (!phoneFit && window.matchMedia('(max-width: 991.98px)').matches) {
            // Small screens (the page scrolls): the field takes the whole width, the card adapts
            // its height
            fitWidth = view.clientWidth
        } else {
            const margin = phoneFit ? 0 : 12
            const width = view.clientWidth - 2 * margin
            const height = view.clientHeight - 2 * margin
            if (width <= 0 || height <= 0) return
            fitWidth = Math.min(width, height * ratio)
        }
        if (fitWidth <= 0) return
        back.style.width = Math.floor(fitWidth) + "px"
        back.style.height = Math.floor(fitWidth / ratio) + "px"
    }

    function resizeCanvases() {
        fitBackground()
        updateRatios()
        const back = document.getElementById('back')
        for (const id of ["robots", "ball"]) {
            const c = document.getElementById(id)
            c.width = back.offsetWidth
            c.height = back.offsetHeight
            c.style.width = back.offsetWidth + "px"
            c.style.height = back.offsetHeight + "px"
        }
    }

    function screenToWorld(screenX, screenY) {
        const back = document.getElementById('back')
        return [
            (screenX - back.offsetWidth  / 2) / ratio_w,
        -(screenY - back.offsetHeight / 2) / ratio_h,
        ]
    }

    function getRatioW() { return ratio_w }

    function drawBg(callback) {
        var background = new Image()
        background.src = "static/imgs/field.svg"
        background.onload = function () {
            let context = document.getElementById('back').getContext('2d')
            context.canvas.width = this.naturalWidth
            context.canvas.height = this.naturalHeight
            context.drawImage(background, 0, 0)
            if (callback) callback()
        }
    }

    // The field area can change size without the window being resized (e.g. alerts)
    const fieldView = document.querySelector('.field-view')
    if (fieldView && window.ResizeObserver) {
        new ResizeObserver(function () {
            if (document.body.classList.contains('sim-view')) {
                resizeCanvases()
            }
        }).observe(fieldView)
    }

    return { renderFrame, resizeCanvases, updateRatios, transformViewToSim, screenToWorld, getRatioW, drawBg }
}