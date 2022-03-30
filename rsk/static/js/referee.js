function referee_initialize(backend)
{
    setInterval(function() {
        
    }, 50);

    // Starting the video capture
    $('.start-referee').click(function() {
        backend.startReferee();
        $('.PlcmPLayer').addClass('referee-running');
    });

    $('.stop-referee').click(function() {
        backend.stopReferee();
        $('.PlcmPLayer').removeClass('referee-running');
    });

}