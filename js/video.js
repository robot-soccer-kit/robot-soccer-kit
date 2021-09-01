function video_initialize(backend)
{
    backend.cameras(function(indexes) {
        let options = '';
        for (let index of indexes) {
            options += "<option value="+index+">Camera "+index+"</option>";
        }
        $('.cameras').html(options);
    });

    // Camera settings
    function sendSettings() {
        backend.cameraSettings($('.brightness').val(), $('.contrast').val());
    }
    $('.brightness').change(sendSettings);
    $('.contrast').change(sendSettings);

    // Starting the video capture
    $('.start-capture').click(function() {
        backend.startCapture($('.cameras').val());
        sendSettings();
    });

    // Retrieving the images
    setInterval(function() {
        backend.getImage(function(image) {
            if (image) {
                $('body').addClass('vision-running');
                $('.camera-image').attr('src', 'data:image/jpeg;base64,'+image);
            }
        });
    }, 50);
}