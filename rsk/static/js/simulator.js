function simulator_initialize(backend)
{
    backend.constants(function(constants) {
        function getMetersToPixelsRatio(){
            return document.getElementById('back').offsetWidth / carpetSize[0]
        }

        function transformViewToSim(position, orientation){
            let simulatorPos = [0.0, 0.0, 0.0]
            let pos = [position[0],position[1],orientation]
            let ratio_w = document.getElementById('back').offsetWidth / carpetSize[0]
            let ratio_h = document.getElementById('back').offsetHeight / carpetSize[1]
            simulatorPos[0] = ((pos[0] + carpetSize[0]/2)* ratio_w)
            simulatorPos[1] = ((-pos[1] + carpetSize[1]/2) * ratio_h) 
            simulatorPos[2] = round(-pos[2]+Math.PI/2)
            return simulatorPos  
        }

        function isDifferent(lastPos, position){
            minimumTranslation = 1
            minimumRotation = 0.05
            if (Math.abs(lastPos[0] - position[0]) > minimumTranslation){
                    return true
            }else if (Math.abs(lastPos[1] - position[1]) >  minimumTranslation){
                    return true
            }else if (Math.abs(lastPos[2] - position[2]) > minimumRotation){
                    return true
            }
            return false
        }

        function drawLeds(color, context){
            for(i = -30; i<-30+120*3; i+= 120){
                angle =  i * Math.PI/180
                x = Math.round(Math.cos(angle)*constants["robot_radius"]*getMetersToPixelsRatio()*0.93)
                y = Math.round(Math.sin(angle)*constants["robot_radius"]*getMetersToPixelsRatio()*0.93)
                context.beginPath()
                gradient = context.createRadialGradient(x, y, 0, x, y, 70);
                gradient.addColorStop(0.05, "rgba("+color+",1)");
                gradient.addColorStop(0.1, "rgba("+color+",0.5)");
                gradient.addColorStop(0.25, "rgba("+color+",0)");
                context.fillStyle = gradient
                context.fillRect(x-25, y-25, 200, 200);
            }
        }

        function drawCircle(position, radius, color, canvas, clear=false, tickness=0){
            context = canvas.getContext('2d')
            if(clear) context.clearRect(0,0,canvas.width,canvas.height)
            context.beginPath()
            context.strokeStyle = color
            context.fillStyle = color
            context.arc(position[0], position[1], radius, 0, Math.PI*2);
            context.lineWidth = tickness    
            if(tickness==0) context.fill()
            else context.stroke()
        }

        function drawBall(position){
            ball = transformViewToSim(position)
            ballCanvas = document.getElementById("ball")
            ballRadius = constants["ball_radius"] * getMetersToPixelsRatio()
            drawCircle(ball, ballRadius, "orange", ballCanvas, true)
        }

        function UpdateView(){

            // FPS Limit
            backend.get_state(function(state) {

                if (state.simulated){
                    tick += 1
                    if (Date.now()-T0 > 100){
                        $('.fps').text("FPS : " + Math.round(1000/((Date.now()-T0)/tick)));
                        T0 = Date.now()
                        tick = 0
                    }
                }

                // Remove missing Robot
                let presentMarker = state.markers
                for (var key in markers) {
                    if(!(key in presentMarker)){
                        canvas = markers[key]["context"].canvas
                        markers[key]["context"].clearRect(0,0,canvas.width,canvas.height)
                        markers[key]["clear"] = true
                    }
                }
                // Draw present Robot
                for (var entry in presentMarker) {

                    robot = presentMarker[entry]
                    robotPos = transformViewToSim(robot.position,robot.orientation)

                    // Draw present Robot that have changed state
                    if (isDifferent(markers[entry]["pos"], robotPos) || markers[entry]["clear"] || markers[entry]["pos"] != state["leds"][entry]) {

                        canvas = markers[key]["context"].canvas
                        markers[entry]["context"].clearRect(-2*canvas.width,-2*canvas.height,4*canvas.width,4*canvas.height)

                        // Context placement
                        markers[entry]["context"].rotate(-markers[entry]["pos"][2])
                        markers[entry]["context"].translate(robotPos[0]-markers[entry]["pos"][0],robotPos[1]-markers[entry]["pos"][1])
                        markers[entry]["context"].rotate(robotPos[2])

                        // Draw leds
                        if (Object.keys(state["leds"]).length != 0){
                            markers[entry]["leds"] = state["leds"][entry]
                            for (var i = 0; i < 3; i++) {
                                markers[entry]["leds"][i] = Math.round(Math.min(255, 50+Math.log(markers[entry]["leds"][i]+1)/Math.log(256) * 255))
                            }
                            drawLeds(markers[entry]["leds"], markers[entry]["context"])
                        }

                        let robotSize = constants["robot_radius"] * 2 * getMetersToPixelsRatio()
                        markers[entry]["context"].drawImage(markers[entry]["image"],-robotSize/2,-robotSize/2,robotSize,robotSize)                 
                        markers[entry]["pos"] = robotPos
                        markers[entry]["clear"] = false

                    }
                }
                //Draw Ball and placement circle 
                backend.get_wait_ball_position(function(placementCirclePosition){
                    if (state.ball != null){
                        drawBall(state.ball)
                    }
                    if (placementCirclePosition != null){
                        drawCircle(transformViewToSim(placementCirclePosition), 20, "red", document.getElementById("ball"), false, 1)
                    }
                })

            });
        }

        function resizeCanvas(canvas){
                backgroundCanvas = document.getElementById('back')
                canvas.width = backgroundCanvas.offsetWidth
                canvas.height = backgroundCanvas.offsetHeight
                return canvas
        }

        function runView(){
            $('#ViewChange').html("<i class='bi bi-camera'></i> Camera View")
            $('#vision').addClass('d-none')
            $('#back').removeClass('d-none')
            $('.sim_vim').css('opacity', '100')

            // Draw Background
            var background = new Image()
            background.src = "static/imgs/field.svg"
            background.onload = function(){
                let context = document.getElementsByTagName('canvas')[0].getContext('2d')
                context.canvas.width = this.naturalWidth
                context.canvas.height = this.naturalHeight
                context.drawImage(background,0,0)
            }

            markers = {"blue1":NaN, "blue2":NaN, "green1":NaN, "green2":NaN}
            for(let marker in markers){
                markers[marker] = {"image":NaN,"context":NaN,"pos":[0,0,0],"leds":[0,0,0],"clear":true}
            }
            for (var key in markers) {
                markers[key]["image"] = new Image();
                markers[key]["image"].src = "static/imgs/robot"+ key +".svg"
                canvas = resizeCanvas(document.getElementById(key))
                markers[key]["context"] = canvas.getContext('2d')
            }
            resizeCanvas(document.getElementById("ball"))

            clearInterval(intervalId)
            intervalId = setInterval(UpdateView, 1000/30)
        } 

        function clearView(){
            clearInterval(intervalId)
            intervalId = NaN
            $('#ViewChange').html("<i class='bi bi-camera'></i> Simulated View")
            $('#vision').removeClass('d-none')
            $('#back').addClass('d-none')
            $('.sim_vim').css('opacity', '0')
        }

        function switchView(){
            if (isNaN(intervalId)){
                runView()
            }else{
                clearView()
            }
        }

        const carpetSize = [constants["carpet_length"], constants["carpet_width"]]
        intervalId = NaN
        let selectedObjet = "ball"
        let tick = 0
        let T0 = Date.now()

        setTimeout(runView, 1000)
        runView()
        window.onresize = runView
        $('#ViewChange').click(switchView)

        backend.is_simulated(function (isSimulated) {
            if(isSimulated) {
                $('body').addClass('vision-running')
                const canvas = document.getElementById("ball")
                const distance = (x1, y1, x2, y2) => Math.hypot(x2 - x1, y2 - y1); 
                let dragType = null
                let initialPosition = null
 
                function teleportSelectedObjectOnMouse(e){
                    let reelPos = [0.0, 0.0, 0.0]
                    pos = [...initialPosition]

                    if (dragType == "position") {
                        pos[0] = e.layerX
                        pos[1] = e.layerY
                    } else {
                        pos[2] = Math.atan2(e.layerY - initialPosition[1], e.layerX - initialPosition[0]) + Math.PI/2
                    }

                    backgroundCanvas = document.getElementById('back')
                    ratio = 1/getMetersToPixelsRatio()
                    reelPos[0] = (pos[0] - backgroundCanvas.offsetWidth/2) * ratio
                    reelPos[1] = -(pos[1] - backgroundCanvas.offsetHeight/2) * ratio
                    reelPos[2] = -(pos[2]-Math.PI/2)
                    backend.teleport(selectedObjet, reelPos[0], reelPos[1], reelPos[2])
                }

                canvas.addEventListener("mousedown", function(e) {
                    for (let marker in markers){
                        if (distance(markers[marker]["pos"][0], markers[marker]["pos"][1], e.layerX, e.layerY) < constants["robot_radius"]*getMetersToPixelsRatio()){
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
                canvas.addEventListener("mouseup", function(e){ 
                    teleportSelectedObjectOnMouse(e)
                    canvas.removeEventListener("mousemove",teleportSelectedObjectOnMouse)
                    selectedObjet = "ball"
                })
            }
        })
        

    })
}