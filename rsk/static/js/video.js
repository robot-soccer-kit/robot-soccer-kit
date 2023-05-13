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
        backend.get_display_settings(false, function(display_settings) {

            let html = ''
            for (setting_name in display_settings) {
                let setting = display_settings[setting_name]
                let checked = setting["value"] ? 'checked="checked"' : ''

                html += '<div class="form-check form-switch">'
                html += '    <input class="form-check-input display-setting" type="checkbox" '
                html += 'role="switch" rel="'+setting_name+'" '+checked+'>'
                html += '    <label class="form-check-label" for="flexSwitchCheckDefault">'
                html += '    '+setting['label']
                html += '    </label>'
                html += '</div>'
            }
            $('.display-settings').html(html)

            $('.display-setting').click(function() {
                backend.set_display_setting($(this).attr('rel'), $(this).is(':checked'));
            });
        });
    }

    $('.display-python-settings').click(function() {
        get_display_settings()
    });

    $('#default-settings').click(function() {
        backend.get_display_settings(true, function(display_settings) {
            for (setting_name in display_settings) {
                $('.display-setting[rel="'+setting_name+'"]').prop('checked', display_settings[setting_name]["default"])
            }
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
