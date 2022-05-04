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

    function get_display_settings() {
        backend.get_display_settings(function(display_settings_bool) {
            $('#aruco').prop('checked', display_settings_bool[0]);
            $('#goals').prop('checked', display_settings_bool[1]);
            $('#ball').prop('checked', display_settings_bool[2]);
            $('#timed_circle').prop('checked', display_settings_bool[3]);
            $('#sideline').prop('checked', display_settings_bool[4]);
            $('#landmark').prop('checked', display_settings_bool[5]);
        });
    }

    $('#apply-settings').click(function() {
        let aruco = $('#aruco:checked').val();
        let goals = $('#goals:checked').val();
        let ball = $('#ball:checked').val();
        let timed_circle = $('#timed_circle:checked').val();
        let sideline = $('#sideline:checked').val();
        let landmark = $('#landmark:checked').val();
        display_settings = [aruco,goals,ball, timed_circle, sideline, landmark]
        backend.set_display_settings(display_settings)
        backend.save_display_settings()
    });

    $('.display-python-settings').click(function() {
        get_display_settings()
    });

    $('#default-settings').click(function() {
        backend.get_default_display_settings(function(display_settings_bool) {
            $('#aruco').prop('checked', display_settings_bool[0]);
            $('#goals').prop('checked', display_settings_bool[1]);
            $('#ball').prop('checked', display_settings_bool[2]);
            $('#timed_circle').prop('checked', display_settings_bool[3]);
            $('#sideline').prop('checked', display_settings_bool[4]);
            $('#landmark').prop('checked', display_settings_bool[5]);
        });
    });

    $('.calibrate-camera').click(function() {
        backend.calibrate_camera()
    });

    // Camera settings
    $.get('static/camera-setting.html', function(template) {
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

    $('.camera-settings').change(function() {
        backend.calibrate_camera()
    });

    // Starting the video capture
    $('.start-capture').click(function() {
        backend.start_capture($('.cameras').val(), $('.resolutions').val());
    });

    $('.stop-capture').click(function() {
        backend.stop_capture();
    });

    // Retrieving the images
    setInterval(function() {
        is_vision = current_tab == 'vision' || 'referee';
        backend.enableVideoDebug(is_vision);

        backend.get_video(is_vision, function(video) {
            if (video.image) {
                $('.camera-image').attr('src', 'data:image/jpeg;base64,'+video.image);
            }
        
            if (video.running) {
                $('body').addClass('vision-running');
            } else {
                $('body').removeClass('vision-running');
            }

            $('.fps').text("FPS : " + video.fps.toFixed(1));

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
                $('.calibrated').html('<i class="bi bi-check2-circle text-success"></i> Field detected and calibrated');
            } else {
                if (video.detection.calibrated) {
                    $('.calibrated').html('<i class="text-warning bi bi-exclamation-circle"></i> Can\'t see whole field, all the green area should be visible</i>');
                } else {
                    $('.calibrated').html('<i class="text-warning bi bi-exclamation-circle"></i> Not calibrated (should see the four field markers)</i>');
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