function robots_initialize(backend)
{
    backend.listPorts(function(ports) {
        let options = '';

        for (let port of ports) {
            options += '<option value="'+port+'">'+port+'</option>';
        }

        $('.ports').html(options);
    });
}