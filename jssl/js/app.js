$(document).ready(function() {
    // Backend initialization
    var backend = null;
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;

        video_initialize(backend);
        robots_initialize(backend);
        control_initialize(backend);
    });

    // (dev) Reload the window
    $('.reload').click(function() {
        window.location.reload();
    });
});