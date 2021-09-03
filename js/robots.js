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
            let html = '';

            // Last communication message
            html += 'last message: ';
            if (infos.last_message) {
                html += Math.round(infos.last_message, 2)+'s';
            } else {
                html += 'never';
            }
            if (!infos.last_message || infos.last_message > 10) {
                html += ' '+warning;
            }
            html += '<br/>';


            // Battery level
            if ('battery' in infos.state) {
                for (let k=0; k<=1; k++) {
                    let voltage = infos.state.battery[k];
                    html += 'battery '+(k+1)+': '+voltage+'V';
                    if (voltage < 3.5) {
                        html += warning;
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
        }

        setInterval(function() {
            backend.getRobots(function(robots) {
                console.log(robots);
                for (let port in robots) {
                    let div = $('.robot[rel="'+port+'"]');
                    if (!div.length) {
                        let html = robot_template.replace(/{port}/g, port);
                        console.log(html);
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
                    }

                    updateInfos(div, robots[port]);
                }

                $('.robot').each(function() {
                    let existingRobot = $('.robot');
                    for (let robot of existingRobot) {
                        if (!($(this).attr('rel') in robots)) {
                            $(this).remove();
                        }
                    }
                });
            });
        }, 100);

    });
}