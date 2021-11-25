function video_initialize(backend)
{
    function updateCameras() {
        backend.cameras(function(data) {
            indexes = data[0]
            favourite_index = data[1]
            let options = '';
            for (let index of indexes) {
                let selected = '';
                if (index == favourite_index) {
                    selected = 'selected="selected"';
                }
                options += "<option value="+index+" "+selected+">Camera "+index+"</option>";
            }
            $('.cameras').html(options);
        });
        backend.resolutions(function(data) {
            let options = '';
            let resolution = data[0];
            let resolutions = data[1];
            for (let index in resolutions) {
                let selected = '';
                if (index == resolution) {
                    selected = 'selected="selected"';
                }
                options += '<option value="'+index+'" '+selected+'>'+resolutions[index]+'</option>';
            }
            $('.resolutions').html(options);
        });
    }
    updateCameras();
    $('.refresh-cameras').click(updateCameras);

    // Camera settings
    $.get('camera-setting.html', function(template) {
        backend.getCameraSettings(function(settings) {
            for (let key in settings) {
                $('.camera-settings').append(template.replace(/{key}/g, key));
                $('.'+key).val(settings[key]);
    
                $('.camera-settings .'+key).change(function() {
                    settings[key] = parseInt($(this).val());
                    backend.cameraSettings(settings);
                });
            }
        });
    });

    // Starting the video capture
    $('.start-capture').click(function() {
        backend.startCapture($('.cameras').val(), $('.resolutions').val());
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

            if (video.detection.calibrated && video.detection.see_whole_field) {
                $('.calibrated').text('Field calibrated');
                $('.calibrated').addClass('text-success');
                $('.calibrated').removeClass('text-danger');
            } else {
                if (video.detection.calibrated) {
                    $('.calibrated').html('Can\'t see whole field <i class="text-warning bi bi-exclamation-circle"></i>');
                } else {
                    $('.calibrated').html('Field not calibrated <i class="text-warning bi bi-exclamation-circle"></i>');
                }
                $('.calibrated').removeClass('text-success');
                $('.calibrated').addClass('text-danger');
            }

            if (video.running && video.detection.calibrated && video.detection.see_whole_field) {
                $('body').addClass('vision-no-error');
            } else {
                $('body').removeClass('vision-no-error');
            }
        });
    }, 50);
}