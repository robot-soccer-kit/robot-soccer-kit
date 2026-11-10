// Vision tab: camera, detection, camera settings, display settings and lens calibration

function video_initialize(backend) {
    // Cameras and resolutions
    function updateCameras() {
        backend.cameras(function (data) {
            let [indexes, favourite, names] = [data[0], data[1], data[2] || {}];
            let options = '';
            for (let index of indexes) {
                let name = names[index] ? ' (' + escapeHtml(names[index]) + ')' : '';
                options += '<option value="' + index + '"' + (index == favourite ? ' selected' : '') + '>'
                    + 'Camera ' + index + name + '</option>';
            }
            if (!indexes.length) {
                options = '<option value="" disabled selected>No camera found</option>';
            }
            $('.cameras').html(options);
            $('.start-capture').prop('disabled', !indexes.length);
        });
        backend.resolutions(function (data) {
            let [current, resolutions] = data;
            let options = '';
            for (let index in resolutions) {
                options += '<option value="' + index + '"' + (index == current ? ' selected' : '') + '>'
                    + escapeHtml(resolutions[index]) + '</option>';
            }
            $('.resolutions').html(options);
        });
    }

    updateCameras();
    $('.refresh-cameras').click(updateCameras);

    $('.start-capture').click(function () {
        backend.start_capture($('.cameras').val(), $('.resolutions').val());
    });

    $('.stop-capture').click(function () {
        backend.stop_capture();
        // The list of cameras can only be retrieved when no camera is used
        setTimeout(updateCameras, 1000);
    });

    $('.calibrate-camera').click(function () {
        backend.calibrate_camera();
    });

    // Display settings (what is drawn on the camera image), in the settings panel
    function renderDisplaySettings(settings) {
        let html = '';
        for (let name in settings) {
            html += '<div class="form-check form-switch">'
                + '<input class="form-check-input display-setting" type="checkbox" role="switch" id="display-' + name + '" rel="' + name + '"'
                + (settings[name].value ? ' checked' : '') + '>'
                + '<label class="form-check-label" for="display-' + name + '">' + escapeHtml(settings[name].label) + '</label>'
                + '</div>';
        }
        $('.display-settings').html(html);
    }

    $('#settings-panel').on('show.bs.offcanvas', function () {
        backend.get_display_settings(false, renderDisplaySettings);
    });
    $('.display-settings').on('change', '.display-setting', function () {
        backend.set_display_setting($(this).attr('rel'), $(this).is(':checked'));
    });
    $('.default-settings').click(function () {
        backend.get_display_settings(true, renderDisplaySettings);
    });

    // Camera settings, by group. The ranges of the image settings are the ones of the camera, when
    // they are known (Linux), else these settings are numbers
    const SETTINGS_GROUPS = [
        ['Image', ['brightness', 'contrast', 'saturation', 'gain', 'exposure']],
        ['Framing', ['crop_x', 'crop_y', 'rescale']],
        ['Lens', ['focal']],
    ];
    const SETTINGS = {
        brightness: { label: 'Brightness' },
        contrast: { label: 'Contrast' },
        saturation: { label: 'Saturation' },
        gain: { label: 'Gain' },
        exposure: { label: 'Exposure' },
        crop_x: { label: 'Crop width', min: 10, max: 100, unit: '%' },
        crop_y: { label: 'Crop height', min: 10, max: 100, unit: '%' },
        rescale: { label: 'Rescale', min: 10, max: 100, unit: '%' },
        focal: { label: 'Focal', unit: 'px' },
    };
    let cameraSettings = {};
    let cameraControls = {};

    function settingRow(key, value) {
        let setting = SETTINGS[key] || { label: key.replace('_', ' ') };
        let range = cameraControls[key] || (setting.min !== undefined ? setting : null);
        let id = 'camera-setting-' + key;
        let html = '<div class="camera-setting-row" rel="' + key + '">'
            + '<label class="form-label mb-0" for="' + id + '">' + escapeHtml(setting.label) + '</label>';
        if (range) {
            html += '<input type="range" class="form-range camera-setting-range" rel="' + key + '"'
                + ' min="' + range.min + '" max="' + range.max + '" step="' + (range.step || 1) + '"'
                + ' value="' + escapeHtml(value) + '" aria-label="' + escapeHtml(setting.label) + '">';
        } else {
            html += '<span></span>';
        }
        html += '<div class="input-group input-group-sm">'
            + '<input type="number" class="form-control camera-setting" id="' + id + '" rel="' + key + '"'
            + ' value="' + escapeHtml(value) + '">'
            + (setting.unit ? '<span class="input-group-text">' + setting.unit + '</span>' : '')
            + '</div>';
        if (cameraControls[key]) {
            html += '<button class="btn btn-sm btn-link camera-setting-default" type="button" rel="' + key + '"'
                + ' title="Default of the camera: ' + cameraControls[key].default + '">'
                + '<i class="bi bi-arrow-counterclockwise"></i></button>';
        } else {
            html += '<span></span>';
        }
        return html + '</div>';
    }

    function renderCameraSettings() {
        let html = '';
        let shown = new Set();
        for (let [group, keys] of SETTINGS_GROUPS) {
            let rows = keys.filter(key => key in cameraSettings);
            if (!rows.length) {
                continue;
            }
            html += '<div class="camera-settings-group"><div class="section-title">' + group + '</div>';
            for (let key of rows) {
                html += settingRow(key, cameraSettings[key]);
                shown.add(key);
            }
            if (group == 'Image' && cameraControls.exposure) {
                html += '<div class="form-text mt-0">Exposure in 0.1 ms: a long exposure blurs the moving robots</div>';
            }
            html += '</div>';
        }
        let others = Object.keys(cameraSettings).filter(key => !shown.has(key));
        if (others.length) {
            html += '<div class="camera-settings-group"><div class="section-title">Other</div>';
            for (let key of others) {
                html += settingRow(key, cameraSettings[key]);
            }
            html += '</div>';
        }
        $('.camera-settings').html(html);
    }

    function loadCameraSettings() {
        backend.camera_controls(function (controls) {
            cameraControls = controls || {};
            backend.getCameraSettings(function (settings) {
                cameraSettings = settings;
                renderCameraSettings();
            });
        });
    }
    loadCameraSettings();

    function sendCameraSettings() {
        // All the values are read from the inputs, since some of them can be updated by the
        // backend (e.g. the focal, by the lens calibration)
        $('.camera-setting').each(function () {
            let value = parseInt($(this).val());
            if (!isNaN(value)) {
                cameraSettings[$(this).attr('rel')] = value;
            }
        });
        backend.cameraSettings(cameraSettings);
        backend.calibrate_camera();
    }

    function setSettingValue(key, value) {
        $('.camera-setting[rel="' + key + '"], .camera-setting-range[rel="' + key + '"]').val(value);
    }

    // Sliders: the value is shown while moving, sent when released
    $('.camera-settings').on('input', '.camera-setting-range', function () {
        $('.camera-setting[rel="' + $(this).attr('rel') + '"]').val($(this).val());
    });
    $('.camera-settings').on('change', '.camera-setting-range', sendCameraSettings);
    $('.camera-settings').on('change', '.camera-setting', function () {
        $('.camera-setting-range[rel="' + $(this).attr('rel') + '"]').val($(this).val());
        sendCameraSettings();
    });
    $('.camera-settings').on('click', '.camera-setting-default', function () {
        let key = $(this).attr('rel');
        setSettingValue(key, cameraControls[key].default);
        sendCameraSettings();
    });

    // Refreshing the camera settings (e.g. after a lens calibration)
    $(document).on('rsk:camera-settings', loadCameraSettings);

    // Automatic settings
    function showAutoStatus(kind, html) {
        $('.auto-settings-status')
            .removeClass('d-none alert-info alert-success alert-warning alert-danger')
            .addClass('alert alert-' + kind + ' py-2 px-3 small')
            .html(html);
    }

    function pollAutoSettings() {
        backend.auto_camera_settings_status(function (status) {
            if (status.state == 'running') {
                setTimeout(pollAutoSettings, 300);
                return;
            }
            $('.auto-camera-settings').prop('disabled', false);
            $('.camera-settings').removeClass('busy');
            if (status.state == 'done') {
                let dark = status.message.includes('more light');
                showAutoStatus(dark ? 'warning' : 'success',
                    '<i class="bi ' + (dark ? 'bi-exclamation-triangle' : 'bi-check-circle') + '"></i> '
                    + escapeHtml(status.message));
            } else if (status.state == 'error') {
                showAutoStatus('danger', '<i class="bi bi-x-circle"></i> ' + escapeHtml(status.message));
            } else {
                $('.auto-settings-status').addClass('d-none');
            }
            loadCameraSettings();
        });
    }

    $('.auto-camera-settings').click(function () {
        $(this).prop('disabled', true);
        $('.camera-settings').addClass('busy');
        showAutoStatus('info', '<span class="spinner-border spinner-border-sm"></span> '
            + 'Adjusting the camera settings: keep the field visible...');
        // On an error (e.g. no image), the error is notified and the state stays idle
        backend.auto_camera_settings();
        setTimeout(pollAutoSettings, 500);
    });

    $('.auto-crop').click(function () {
        backend.auto_crop(function (crop) {
            if (crop.too_small) {
                showAutoStatus('warning', '<i class="bi bi-exclamation-triangle"></i> The field and its border are '
                    + 'not entirely in the camera image: the camera should see a larger area');
            } else {
                showAutoStatus('success', '<i class="bi bi-check-circle"></i> Image cropped to '
                    + crop.crop_x + ' % x ' + crop.crop_y + ' %, keeping a border around the field '
                    + 'to see the robots leaving it');
            }
            loadCameraSettings();
        });
    });

    // Video status and images
    let wasRunning = false;
    function updateStatus(video) {
        let running = video.running;
        let detection = video.detection;
        $('body').toggleClass('vision-running', running);

        let status = 'error', title = 'The vision is not running', message = '';
        if (running && video.no_image) {
            message = '<i class="bi bi-exclamation-triangle-fill text-danger"></i> No image from the camera: '
                + 'is it used by another program? Try to stop and start the vision, or another camera';
            title = 'No image from the camera';
        } else if (running && detection.calibrated && detection.see_whole_field) {
            status = 'ok';
            title = 'The vision is running, the field is calibrated';
            message = '<i class="bi bi-check-circle-fill text-success"></i> Field detected and calibrated';
        } else if (running && detection.calibrated) {
            status = 'warning';
            title = 'The whole field is not visible';
            message = '<i class="bi bi-exclamation-triangle-fill text-warning"></i> The whole field is not '
                + 'visible: all the green area should be in the image';
        } else if (running) {
            status = 'warning';
            title = 'The field is not calibrated';
            message = '<i class="bi bi-exclamation-triangle-fill text-warning"></i> Field not calibrated: '
                + 'the four field markers should be visible';
        }
        $('.vision-status').removeClass('ok warning error').addClass(status).attr('title', title);
        $('.auto-crop').prop('disabled', !(running && detection.calibrated));

        // The ranges of the settings are known once the camera is opened
        if (running && !wasRunning) {
            loadCameraSettings();
        }
        wasRunning = running;
        $('.calibrated').html(message);
        $('.fps').text(running ? 'FPS: ' + Math.round(video.fps) : 'FPS: -');

        // Detected objects
        let html = '';
        if (detection.ball) {
            html += '<div><span class="badge text-bg-warning me-2">ball</span>x = ' + round(detection.ball[0])
                + ', y = ' + round(detection.ball[1]) + '</div>';
        }
        for (let entry of Object.keys(detection.markers || {}).sort()) {
            let marker = detection.markers[entry];
            let team = robotTeamNumber(entry)[0];
            let badge = ['green', 'blue'].includes(team) ? 'bg-team team-' + team : 'text-bg-secondary';
            html += '<div><span class="badge ' + badge + ' me-2">' + escapeHtml(entry) + '</span>'
                + 'x = ' + round(marker.position[0]) + ', y = ' + round(marker.position[1])
                + ', orientation = ' + round(marker.orientation) + '</div>';
        }
        $('.detection').html(html || '<span class="text-body-secondary">Nothing detected</span>');
    }

    setInterval(function () {
        let withImage = current_tab == 'vision' || current_tab == 'referee';
        backend.enableVideoDebug(withImage);
        backend.get_video(withImage, function (video) {
            if (video.image) {
                $('.camera-image').attr('src', 'data:image/jpeg;base64,' + video.image);
            }
            updateStatus(video);
        });
    }, 50);

    lens_calibration_initialize(backend);
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
                html += '<td style="background: ' + color
                    + '" title="' + count + ' corners"></td>';
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
            $(document).trigger('rsk:camera-settings');
        });
    });
    $('.lens-remove').click(function() {
        confirmDialog('Remove the lens calibration? The focal setting will be used again.', function () {
            backend.remove_lens_calibration(update);
        }, 'Remove');
    });
}
