function video_initialize(backend)
{
    function updateCameras() {
        backend.cameras(function(indexes) {
            let options = '';
            for (let index of indexes) {
                options += "<option value="+index+">Camera "+index+"</option>";
            }
            $('.cameras').html(options);
        });
    }
    updateCameras();
    $('.refresh-cameras').click(updateCameras);

    // Camera settings
    function sendSettings() {
        backend.cameraSettings($('.brightness').val(), $('.contrast').val(), $('.saturation').val());
    }
    $('.brightness').change(sendSettings);
    $('.contrast').change(sendSettings);
    $('.saturation').change(sendSettings);

    // Starting the video capture
    $('.start-capture').click(function() {
        backend.startCapture($('.cameras').val());
        sendSettings();
    });

    $('.stop-capture').click(function() {
        backend.stopCapture();
    });

    // Retrieving the images
    setInterval(function() {
        is_vision = current_tab == 'vision';
        backend.enableVideoDebug(is_vision);

        backend.getVideo(is_vision, function(video) {
            if (video.image) {
                $('.camera-image').attr('src', 'data:image/jpeg;base64,'+video.image);
            }
        
            if (video.running) {
                $('body').addClass('vision-running');
            } else {
                $('body').removeClass('vision-running');
            }

            $('.fps').text(video.fps);

            let detection = ''
            if (video.detection.ball) {
                detection += 'ball: x='+round(video.detection.ball[0])+', y='+round(video.detection.ball[1])+"<br>";
            }
            for (let entry in video.detection.markers) {
                let robot = video.detection.markers[entry];
                detection += entry+': x='+round(robot.position[0])+', y='+round(robot.position[1])+', o='+round(robot.orientation)+"<br>";
            }
            if (detection == '') {
                detection = 'no detection';
            }
            $('.detection').html(detection);

            if (video.detection.calibrated) {
                $('.calibrated').text('Field calibrated');
                $('.calibrated').addClass('text-success');
                $('.calibrated').removeClass('text-danger');
            } else {
                $('.calibrated').html('Field not calibrated <i class="text-warning bi bi-exclamation-circle"></i>');
                $('.calibrated').removeClass('text-success');
                $('.calibrated').addClass('text-danger');
            }

            if (video.running && video.detection.calibrated) {
                $('body').addClass('vision-no-error');
            } else {
                $('body').removeClass('vision-no-error');
            }
        });
    }, 50);
}