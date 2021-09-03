function robots_initialize(backend)
{
    backend.listPorts(function(ports) {
        let options = '';

        for (let port of ports) {
            options += '<option value="'+port+'">'+port+'</option>';
        }

        $('.ports').html(options);
    });

    $('.add-robot').click(function() {
        backend.addRobot($('.ports').val());
    });

    $.get('robot.html', function(robot_template) {
        let warning = '<i class="bi text-warning bi-exclamation-circle"></i>';

        function updateInfos(div, infos) {
            let hasWarning = false;
            let html = '';

            // Last communication message
            html += 'last message: ';
            if (infos.last_message) {
                html += (Math.round(infos.last_message*100)/100)+'s';
            } else {
                html += 'never';
            }
            if (!infos.last_message || infos.last_message > 5) {
                html += ' '+warning+' <span class="text-warning">no response</span>';
                hasWarning = true;
            }
            html += '<br/>';


            // Battery level
            if ('battery' in infos.state) {
                for (let k=0; k<=1; k++) {
                    let voltage = infos.state.battery[k];
                    html += 'battery '+(k+1)+': '+voltage+'V';
                    if (voltage < 3.5) {
                        html += ' '+warning+' <span class="text-warning">low voltage</span>';
                        hasWarning = true;
                    }
                    html += '<br/>';
                }
            }

            div.find('.infos').html(html);

            // Marker
            if (infos.marker) {
                $('.marker-image').html('<img src="markers/'+infos.marker+'.svg" class="m-1" width="80" />');
                $('.marker-select').val(infos.marker);
            } else {
                $('.marker-image').html('N/A');
                $('.marker-select').val('none');
            }

            return hasWarning;
        }

        setInterval(function() {
            backend.getRobots(function(robots) {
                let hasWarning = false;
                let robotsOk = 0;
                let robotsCount = 0;

                for (let port in robots) {
                    let div = $('.robot[rel="'+port+'"]');
                    if (!div.length) {
                        let html = robot_template.replace(/{port}/g, port);
                        $('.robots').append(html);

                        let div = $('.robot[rel="'+port+'"]');
                        div.find('.marker-select').change(function() {
                            let marker = $(this).val();
                            if (marker == 'none') {
                                marker = null;
                            }
                            backend.setMarker(port, marker);
                        });

                        div.find('.remove').click(function() {
                            backend.removeRobot(port);
                        });

                        div.find('.blink').click(function() {
                            backend.blink(port);
                        });

                        div.find('.kick').click(function() {
                            backend.kick(port);
                        });
                    }

                    let error = updateInfos(div, robots[port]);
                    robotsCount += 1;
                    if (!error) {
                        robotsOk += 1;
                    }
                    hasWarning = hasWarning || error;
                }

                $('.robots-ok').text(robotsOk);
                $('.robots-count').text(robotsCount);

                $('.robot').each(function() {
                    let existingRobot = $('.robot');
                    for (let robot of existingRobot) {
                        if (!($(this).attr('rel') in robots)) {
                            $(this).remove();
                        }
                    }
                });

                if (hasWarning) {
                    $('body').addClass('robots-warning');
                } else {
                    $('body').removeClass('robots-warning');
                }
            });
        }, 100);

    });
}