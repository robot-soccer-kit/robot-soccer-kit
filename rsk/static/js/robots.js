function robots_initialize(backend)
{
    function updateURLs() {
        backend.available_urls(function(urls) {
            let options = '';

            for (let url of urls) {
                options += '<option value="'+url+'">'+url+'</option>';
            }

            $('.urls').html(options);
        });
    }
    updateURLs();
    function removeOffline(){
        backend.get_robots(function(robots) {
            for (let url in robots) {
                if (!robots[url].last_message || robots[url].last_message > 5) {
                    backend.removeRobot(url)
                }
            }
        });
    }

    $('.remove-offline').click(function (event) {
        event.preventDefault();
        removeOffline();
    });

    $('.refresh-urls').click(function (event) {
        event.preventDefault();
        updateURLs();
    });

    $('.add-robot').click(function(event) {
        event.preventDefault();
        backend.add_robot($('.urls').val());
    });
    $('.add-all-robots').click(function(event) {
        event.preventDefault();
        $('.urls option').each(function() {
            backend.add_robot($(this).val());
        });
    });
    $('.identify').click(function(event) {
        event.preventDefault();
        backend.identify();
    });

    $.get('static/robot.html', function(robot_template) {
        let warning = '<i class="bi text-warning bi-exclamation-circle"></i>';
        let success = '<i class="bi text-success bi-check-circle"></i>';

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
                for (let k in infos.state.battery) {
                    let voltage = infos.state.battery[k];
                    html += 'battery';
                    if (infos.state.battery.length > 1) {
                        html += ' '+(parseInt(k)+1);
                    }
                    html += ': '+voltage+'V';
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
                div.find('.marker-image').html('<img src="static/markers/'+infos.marker+'.svg" class="m-1" width="80" />');
                div.find('.marker-select').val(infos.marker);
            } else {
                div.find('.marker-image').html('N/A');
                div.find('.marker-select').val('none');
            }


        if(infos.marker && (!infos.last_detection || infos.last_detection > 0.15)){
            hasWarning = true;
            div.find('.not-detected').html('Not detected ' + warning);
            div.find('.not-detected').removeClass('invisible');
        }else{
            div.find('.not-detected').addClass('invisible');
        }
            return hasWarning;
        }

        setInterval(function() {
            backend.get_robots(function(robots) {
                let hasWarning = false;
                let robotsOk = 0;
                let robotsCount = 0;

                for (let url in robots) {
                    let div = $('.robot[rel="'+url+'"]');
                    if (!div.length) {
                        let html = robot_template.replace(/{url}/g, url);
                        $('.robots').append(html);

                        let div = $('.robot[rel="'+url+'"]');
                        div.find('.marker-select').change(function() {
                            let marker = $(this).val();
                            if (marker == 'none') {
                                marker = null;
                            }
                            backend.set_marker(url, marker);
                        });

                        div.find('.remove').click(function(event) {
                            event.preventDefault();
                            backend.removeRobot(url);
                        });

                        div.find('.blink').click(function(event) {
                            event.preventDefault();
                            backend.blink(url);
                        });

                        div.find('.kick').click(function(event) {
                            event.preventDefault();
                            backend.kick(url);
                        });
                    }

                    let error = updateInfos(div, robots[url]);
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
        }, 200);

    });
}