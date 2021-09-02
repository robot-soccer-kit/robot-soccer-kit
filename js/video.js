function video_initialize(backend)
{
    backend.cameras(function(indexes) {
        let options = '';
        for (let index of indexes) {
            options += "<option value="+index+">Camera "+index+"</option>";
        }
        $('.cameras').html(options);
    });

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

        if (is_vision) {
            backend.getVideo(function(video) {
                if (video.image) {
                    $('body').addClass('vision-running');
                    $('.camera-image').attr('src', 'data:image/jpeg;base64,'+video.image);
                } else {
                    $('body').removeClass('vision-running');
                }
                $('.fps').text(video.fps);

                let detection = ''
                if (video.detection.ball) {
                    detection += 'ball: '+JSON.stringify(video.detection.ball)+"<br>";
                }
                for (let entry in video.detection.markers) {
                    detection += entry+': '+JSON.stringify(video.detection.markers[entry])+"<br>";
                }
                $('.detection').html(detection);
            });
        }
    }, 50);
}