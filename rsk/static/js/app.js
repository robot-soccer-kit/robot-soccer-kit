class APIBackend {
    constructor(url) {
        return new Proxy(this, {
            get: function get(target, name) {
                return function (...args) {
                    let last = args.length - 1;
                    let callback = null;
                    if (typeof (args[last]) == 'function') {
                        callback = args.pop();
                    }

                    let timeout = 3000;
                    if (name == "cameras") { timeout = 10000 }
                    $.get({
                        "url": url, "data": { 'command': name, 'args': JSON.stringify(args) }, 'success': function (result) {
                            $('.no-backend').css("opacity", '0')
                            if (result) {
                                if (result[0]) {
                                    if (callback) {
                                        callback(result[1]);
                                    }
                                } else {
                                    console.log('Error: ' + result[1]);
                                }
                            }
                        }, "timeout": timeout
                    }).fail(function () {
                        $('.no-backend').css("opacity", '1')
                    });;
                }
            }
        });
    }
}


$(document).ready(function () {
    // Backend initialization
    var backend = new APIBackend('http://127.0.0.1:7070/api');
    backend.is_simulated(function (simulated) {
        if (simulated) {
            console.log("SIMULATION")
            $('.not_show_simulated').css("display", 'none')
            simulator_initialize(backend, true)
        } else {
            console.log("REEL")
            $('.show_simulated').css("display", 'none')
            video_initialize(backend);
            simulator_initialize(backend, false)
        }
    })

    backend.is_competition(function (competition) {
        if (competition) {
            $('.competition-mode').show();
            competition_initialize(backend);
        }
    });

    robots_initialize(backend);
    control_initialize(backend);
    referee_initialize(backend);

    // (dev) Reload the window
    $('.reload').click(function () {
        window.location.reload();
    });
});