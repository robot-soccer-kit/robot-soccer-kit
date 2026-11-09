// Robots tab: adding robots, markers, status (battery, communication, detection)

function robots_initialize(backend) {
    const markers = ['green1', 'green2', 'blue1', 'blue2'];

    function updateURLs() {
        backend.available_urls(function (urls) {
            let options = '';
            for (let url of urls) {
                options += '<option value="' + escapeHtml(url) + '">' + escapeHtml(url) + '</option>';
            }
            if (!urls.length) {
                options = '<option value="" disabled selected>No robot found</option>';
            }
            $('.urls').html(options);
            $('.add-robot, .add-all-robots').prop('disabled', !urls.length);
        });
    }
    updateURLs();

    $('.refresh-urls').click(updateURLs);
    $('.add-robot').click(function () {
        if ($('.urls').val()) {
            backend.add_robot($('.urls').val());
        }
    });
    $('.add-all-robots').click(function () {
        $('.urls option').each(function () {
            if ($(this).val()) {
                backend.add_robot($(this).val());
            }
        });
    });
    $('.identify').click(function () {
        let button = $(this).prop('disabled', true);
        notify('Identifying the robots: each robot turns in turn', 'info');
        backend.identify(function () {
            button.prop('disabled', false);
            notify('Identification done', 'success');
        });
    });
    $('.remove-offline').click(function () {
        backend.get_robots(function (robots) {
            for (let url in robots) {
                if (!robots[url].last_message || robots[url].last_message > 5) {
                    backend.removeRobot(url);
                }
            }
        });
    });

    function robotCard(url) {
        let options = '<option value="none">No marker</option>';
        for (let marker of markers) {
            let [team, number] = robotTeamNumber(marker);
            options += '<option value="' + marker + '">' + capitalize(team) + ' ' + number + '</option>';
        }

        let card = $(
            '<div class="col-md-6 col-xxl-4 robot-col">'
            + '<div class="card robot-card h-100">'
            + '<div class="card-header d-flex align-items-center gap-2">'
            + '<span class="status-dot robot-status-dot"></span>'
            + '<span class="robot-url"></span>'
            + '</div>'
            + '<div class="card-body d-flex gap-3">'
            + '<div class="flex-grow-1 robot-infos"></div>'
            + '<div class="text-center" style="width: 9rem;">'
            + '<select class="form-select form-select-sm mb-2 marker-select" aria-label="Marker">' + options + '</select>'
            + '<div class="marker-image"></div>'
            + '</div>'
            + '</div>'
            + '<div class="card-footer d-flex gap-2">'
            + '<button class="btn btn-sm btn-outline-secondary blink" type="button"><i class="bi bi-lightbulb"></i>&nbsp;Blink</button>'
            + '<button class="btn btn-sm btn-outline-secondary kick" type="button"><i class="bi bi-lightning"></i>&nbsp;Kick</button>'
            + '<button class="btn btn-sm btn-outline-danger ms-auto remove" type="button"><i class="bi bi-trash"></i>&nbsp;Remove</button>'
            + '</div>'
            + '</div>'
            + '</div>'
        );
        card.attr('data-url', url);
        card.find('.robot-url').text(url);

        card.find('.marker-select').change(function () {
            let marker = $(this).val();
            backend.set_marker(url, marker == 'none' ? null : marker);
        });
        card.find('.remove').click(function () {
            backend.removeRobot(url);
        });
        card.find('.blink').click(function () {
            backend.blink(url);
        });
        card.find('.kick').click(function () {
            backend.kick(url);
        });
        return card;
    }

    // Returns the problems of a robot (empty if none)
    function updateRobotCard(card, infos) {
        let problems = [];
        let html = '';

        // Communication
        html += '<div><i class="bi bi-broadcast"></i> ';
        if (infos.last_message !== null && infos.last_message !== undefined) {
            html += 'Last message ' + round(infos.last_message) + ' s ago';
        } else {
            html += 'No message received';
        }
        if (!infos.last_message || infos.last_message > 5) {
            html += ' <span class="badge text-bg-warning">no response</span>';
            problems.push('no response');
        }
        html += '</div>';

        // Battery
        let batteries = (infos.state && infos.state.battery) || [];
        for (let k = 0; k < batteries.length; k++) {
            let voltage = batteries[k];
            let low = voltage < 3.5;
            html += '<div><i class="bi ' + (low ? 'bi-battery text-danger' : 'bi-battery-full') + '"></i> Battery'
                + (batteries.length > 1 ? ' ' + (k + 1) : '') + ': ' + round(voltage) + ' V'
                + (low ? ' <span class="badge text-bg-danger">low</span>' : '') + '</div>';
            if (low) {
                problems.push('low battery');
            }
        }

        // Detection
        if (infos.marker) {
            let detected = infos.last_detection !== null && infos.last_detection <= 0.15;
            html += '<div><i class="bi bi-eye"></i> '
                + (detected ? 'Detected by the camera' : '<span class="text-warning">Not detected by the camera</span>')
                + '</div>';
            if (!detected) {
                problems.push('not detected');
            }
        } else {
            html += '<div class="text-body-secondary"><i class="bi bi-eye-slash"></i> No marker: '
                + 'select it, or click on "Identify"</div>';
        }

        card.find('.robot-infos').html(html);

        let select = card.find('.marker-select');
        if (!select.is(':focus')) {
            select.val(infos.marker || 'none');
        }
        card.find('.marker-image').html(infos.marker
            ? '<img src="static/markers/' + escapeHtml(infos.marker) + '.svg" alt="' + escapeHtml(infos.marker) + '" />'
            : '');
        card.find('.robot-status-dot')
            .removeClass('ok warning error')
            .addClass(problems.length ? 'warning' : 'ok')
            .attr('title', problems.join(', ') || 'OK');

        return problems;
    }

    setInterval(function () {
        backend.get_robots(function (robots) {
            let ok = 0, count = 0;

            for (let url in robots) {
                let card = $('.robot-col').filter(function () { return $(this).attr('data-url') == url; });
                if (!card.length) {
                    card = robotCard(url);
                    $('.robots').append(card);
                }
                count += 1;
                if (!updateRobotCard(card, robots[url]).length) {
                    ok += 1;
                }
            }

            $('.robot-col').each(function () {
                if (!($(this).attr('data-url') in robots)) {
                    $(this).remove();
                }
            });
            $('.no-robots').toggleClass('d-none', count > 0);

            $('.robots-badge')
                .text(count ? ok + '/' + count : '0')
                .removeClass('text-bg-secondary text-bg-success text-bg-warning')
                .addClass(!count ? 'text-bg-secondary' : (ok == count ? 'text-bg-success' : 'text-bg-warning'))
                .attr('title', ok + ' robots OK out of ' + count);
        });
    }, 500);
}
