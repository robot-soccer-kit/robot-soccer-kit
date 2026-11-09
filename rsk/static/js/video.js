function video_initialize(backend)
{
    function updateCameras() {
        backend.cameras(function(data) {
            indexes = data[0]
            favourite_index = data[1]
            let names = data[2] || {}
            let options = '';
            for (let index of indexes) {
                let selected = '';
                if (index == favourite_index) {
                    selected = 'selected="selected"';
                }
                let name = names[index] ? ' (' + $('<span>').text(names[index]).html() + ')' : '';
                options += "<option value="+index+" "+selected+">Camera "+index+name+"</option>";
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
                    // All the values are read from the inputs, since some of them can be
                    // updated by the backend (e.g. the focal, by the lens calibration)
                    for (let name in settings) {
                        settings[name] = parseInt($('.camera-settings .'+name).val());
                    }
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

    lens_calibration_initialize(backend);

    // Retrieving the images
    setInterval(function() {

        is_vision = (current_tab == 'vision' || current_tab == 'referee');
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

function lens_calibration_initialize(backend)
{
    function round_to(value, digits) {
        return Number(value).toFixed(digits);
    }

    function render_current(status) {
        let current = status.current;
        let html = '';

        if (!status.supported) {
            html = '<i class="bi bi-exclamation-circle text-warning"></i> '
                + 'The installed OpenCV version is too old for the lens calibration (4.7 or newer is needed)';
        } else if (!current) {
            html = '<i class="bi bi-info-circle"></i> '
                + 'Lens not calibrated: the <code>focal</code> setting is used and the lens distortion is ignored';
        } else {
            let date = current.date ? current.date.replace('T', ' ') : '?';
            let summary = 'focal ' + round_to((current.focal_px[0] + current.focal_px[1]) / 2, 0) + ' px, '
                + 'distortion ' + round_to(current.distortion_at_image_corners_px, 0) + ' px in the corners';
            if (status.current_used) {
                html = '<i class="bi bi-check2-circle text-success"></i> '
                    + 'Lens calibrated on ' + date + ' (' + summary + '), used by the vision. '
                    + 'The <code>focal</code> setting was set from this calibration.';
            } else {
                html = '<i class="bi bi-exclamation-circle text-warning"></i> '
                    + 'Lens calibrated on ' + date + ' for a ' + current.image_size.join('x')
                    + ' resolution: not used with the current resolution'
                    + (status.raw_size ? ' (' + status.raw_size.join('x') + ')' : '');
            }
        }
        $('.lens-current').html(html);
        $('.lens-remove').toggle(!!current);
    }

    function render_coverage(status) {
        if (!status.coverage) {
            $('.lens-coverage').html('');
            return;
        }
        let html = '';
        for (let row of status.coverage) {
            html += '<tr>';
            for (let count of row) {
                let color = count == 0 ? '#dc3545' : (count < status.coverage_good ? '#ffc107' : '#198754');
                html += '<td style="width: 28px; height: 18px; background: ' + color
                    + '; border: 1px solid white" title="' + count + ' corners"></td>';
            }
            html += '</tr>';
        }
        $('.lens-coverage').html(html);
    }

    function render_result(result) {
        if (!result) {
            return;
        }
        let rows = [
            ['Views', result.views],
            ['Reprojection error', round_to(result.rms_reprojection_error_px, 2) + ' px'
                + (result.rms_reprojection_error_px > 1 ? ' <span class="text-warning">(high: is the board flat? images blurred?)</span>' : '')],
            ['Focal', round_to(result.focal_px[0], 1) + ' / ' + round_to(result.focal_px[1], 1) + ' px'],
            ['Optical center offset', round_to(result.principal_point_offset_px[0], 1) + ' / '
                + round_to(result.principal_point_offset_px[1], 1) + ' px'],
            ['Distortion in the corners', round_to(result.distortion_at_image_corners_px, 1) + ' px'],
            ['Field of view (diagonal)', round_to(result.diagonal_fov_deg, 1) + '°'],
        ];
        let html = '';
        for (let [name, value] of rows) {
            html += '<tr><th>' + name + '</th><td>' + value + '</td></tr>';
        }
        $('.lens-result').html(html);
    }

    function update() {
        if (current_tab != 'vision') {
            return;
        }
        backend.lens_calibration_status(function(status) {
            $('.lens-state').hide();
            $('.lens-state-' + status.state).show();

            render_current(status);
            $('.lens-start').toggleClass('disabled', !status.supported);

            $('.lens-views').text(status.views);
            $('.lens-min-views').text(status.min_views);

            // A view was just captured
            let just_captured = status.last_capture_age !== null && status.last_capture_age < 1.0;
            $('.lens-views-badge')
                .toggleClass('bg-success', just_captured)
                .toggleClass('bg-secondary', !just_captured);
            $('.lens-captured').html(just_captured ? '<i class="bi bi-camera-fill"></i> View captured!' : '');

            // What is missing to compute the calibration
            let missing = [];
            if (status.missing_views > 0) {
                missing.push(status.missing_views + ' more views needed');
            }
            if (status.missing_cells > 0) {
                missing.push(status.missing_cells + ' zones of the image are not green yet');
            }
            $('.lens-missing').html(missing.length
                ? '<i class="bi bi-hourglass-split"></i> ' + missing.join(', ')
                : '<span class="text-success"><i class="bi bi-check2-circle"></i> '
                    + 'Ready: you can compute the calibration</span>');
            $('.lens-board-visible').html(status.board_visible
                ? '<span class="text-success">board visible</span>'
                : '<span class="text-muted">board not visible</span>');
            $('.lens-compute').toggleClass('disabled', !status.ready);
            render_coverage(status);

            render_result(status.result);
            $('.lens-error').text(status.error || '');
        });
    }

    $('.lens-state').hide();
    setInterval(update, 300);

    $('.lens-start').click(function() {
        backend.start_lens_calibration(update);
    });
    $('.lens-cancel').click(function() {
        backend.cancel_lens_calibration(update);
    });
    $('.lens-compute').click(function() {
        if (!$(this).hasClass('disabled')) {
            backend.compute_lens_calibration(update);
        }
    });
    $('.lens-apply').click(function() {
        backend.apply_lens_calibration(function() {
            update();
            // The focal setting was updated from the calibration
            backend.getCameraSettings(function(settings) {
                for (let key in settings) {
                    $('.camera-settings .' + key).val(settings[key]);
                }
            });
        });
    });
    $('.lens-remove').click(function() {
        if (confirm('Remove the lens calibration? The focal setting will be used again.')) {
            backend.remove_lens_calibration(update);
        }
    });
}
