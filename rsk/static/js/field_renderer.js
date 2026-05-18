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
        context = canvas.getContext('2d')
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
        context = canvas.getContext('2d')
        context.beginPath()
        context.strokeStyle = color
        context.fillStyle = color

        context.moveTo(...begin);
        context.lineTo(...end);
        context.lineWidth = tickness
        context.stroke()
    }
    function drawLeds(color, context) {
        for (i = -30; i < -30 + 120 * 3; i += 120) {
            angle = i * Math.PI / 180
            x = Math.round(Math.cos(angle) * constants["robot_radius"] * ratio_w * 0.93)
            y = Math.round(Math.sin(angle) * constants["robot_radius"] * ratio_w * 0.93)
            context.beginPath()
            gradient = context.createRadialGradient(x, y, 0, x, y, 70);
            gradient.addColorStop(0.05, "rgba(" + color + ",1)");
            gradient.addColorStop(0.1, "rgba(" + color + ",0.5)");
            gradient.addColorStop(0.25, "rgba(" + color + ",0)");
            context.fillStyle = gradient
            context.fillRect(x - 25, y - 25, 200, 200);
        }
    }

    function drawBall(position) {
        ball = transformViewToSim(position)
        ballCanvas = document.getElementById("ball")
        ballRadius = constants["ball_radius"] * ratio_w
        drawCircle(ball, ballRadius, "orange", ballCanvas, true)
    }

    function renderFrame(state, markers, displaySettings = {}) {

        if (!ratio_w) updateRatios()

        let presentMarker = state.markers
        let canvas = document.getElementById("robots")

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
            robot = presentMarker[entry]
            if (!robot) continue
            robotPos = transformViewToSim(robot.position, robot.orientation)

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
            markers[entry]["pos"] = robotPos
            markers[entry]["clear"] = false
        }

        canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height)
        canvas.getContext("2d").drawImage(canvas.offscreenCanvas, 0, 0)

        //Draw Ball and placement circle 
        ballCanvas = document.getElementById("ball")
        ballContext = ballCanvas.getContext("2d")

        if (state.ball != null) {
            drawBall(state.ball)
        }

        // let placementCirclePosition = state["referee"]["wait_ball_position"]
        const placementCirclePosition = state.referee?.wait_ball_position ?? null
        if (placementCirclePosition != null) {
            drawCircle(transformViewToSim(placementCirclePosition), constants.place_ball_margin * ratio_w, "red", ballCanvas, false, 1)
        }

        if (displaySettings["landmark"]?.["value"]) {
            center = [ballCanvas.width / 2, ballCanvas.height / 2]
            drawline(center, [center[0], center[1] - 100], ballCanvas, "green")
            drawline(center, [center[0] + 100, center[1]], ballCanvas, "red")
        }

        if (displaySettings["timed_circle"]?.["value"]) {
            drawCircle(transformViewToSim(state.ball), constants.timed_circle_radius * ratio_w, "red", ballCanvas, false, 1, [10, 10])
        }
    }

    function resizeCanvases() {
        updateRatios()
        const back = document.getElementById('back')
        for (const id of ["robots", "ball"]) {
            const c = document.getElementById(id)
            c.width = back.offsetWidth
            c.height = back.offsetHeight
        }
    }

    // dans createFieldRenderer, à ajouter à l'API publique :
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
            let context = document.getElementsByTagName('canvas')[0].getContext('2d')
            context.canvas.width = this.naturalWidth
            context.canvas.height = this.naturalHeight
            context.drawImage(background, 0, 0)
            if (callback) callback()
        }
    }

    return { renderFrame, resizeCanvases, updateRatios, transformViewToSim, screenToWorld, getRatioW, drawBg }
}