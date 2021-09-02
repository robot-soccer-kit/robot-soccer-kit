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
}