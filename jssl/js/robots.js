function robots_initialize(backend)
{
    function updatePorts() {
        backend.ports(function(ports) {
            let options = '';

            for (let port of ports) {
                options += '<option value="'+port+'">'+port+'</option>';
            }

            $('.ports').html(options);
        });
    }
    updatePorts();
    $('.refresh-ports').click(function (event) {
        event.preventDefault();
        updatePorts();
    });

    $('.add-robot').click(function(event) {
        event.preventDefault();
        backend.addRobot($('.ports').val());
    });
    $('.add-all-robots').click(function(event) {
        event.preventDefault();
        $('.ports option').each(function() {
            backend.addRobot($(this).val());
        });
    });
    $('.identify').click(function(event) {
        event.preventDefault();
        backend.identify();
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
                div.find('.marker-image').html('<img src="markers/'+infos.marker+'.svg" class="m-1" width="80" />');
                div.find('.marker-select').val(infos.marker);
            } else {
                div.find('.marker-image').html('N/A');
                div.find('.marker-select').val('none');
            }

            if (infos.marker && (!infos.last_detection || infos.last_detection > 0.15)) {
                hasWarning = true;
                div.find('.not-detected').html('Not detected ' + warning);
            } else {
                div.find('.not-detected').html('');
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

                        div.find('.remove').click(function(event) {
                            event.preventDefault();
                            backend.removeRobot(port);
                        });

                        div.find('.blink').click(function(event) {
                            event.preventDefault();
                            backend.blink(port);
                        });

                        div.find('.kick').click(function(event) {
                            event.preventDefault();
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