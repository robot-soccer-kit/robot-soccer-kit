$(document).ready(function() {
    var backend = null;
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;

        backend.cameras(function(indexes) {
            let options = '';
            for (let index of indexes) {
                options += "<option value="+index+">Camera "+index+"</option>";
            }
            $('.cameras').html(options);
        });
    });

    $('.reload').click(function() {
        window.location.reload();
    });

    function sendSettings() {
        if (backend) {
            backend.cameraSettings($('.brightness').val(), $('.contrast').val());
        }
    }
    $('.brightness').change(sendSettings);
    $('.contrast').change(sendSettings);

    $('.start-capture').click(function() {
        if (backend) {
            backend.startCapture($('.cameras').val());
            sendSettings();
        }
    });

    setInterval(function() {
        backend.getImage(function(image) {
            $('.camera-image').attr('src', 'data:image/jpeg;base64,'+image);
            console.log(image)
        });
    }, 100);
});