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

                    $.get(url, { 'command': name, 'args': JSON.stringify(args) }, function (result) {
                        if (result) {
                            if (result[0]) {
                                if (callback) {
                                    callback(result[1]);
                                }
                            } else {
                                console.log('Error: ' + result[1]);
                            }
                        }
                    });
                }
            }
        });
    }
}


$(document).ready(function () {
    // Backend initialization
    var backend = new APIBackend('http://127.0.0.1:7070/api');
    video_initialize(backend);
    robots_initialize(backend);
    control_initialize(backend);
    referee_initialize(backend);

    // (dev) Reload the window
    $('.reload').click(function () {
        window.location.reload();
    });
});