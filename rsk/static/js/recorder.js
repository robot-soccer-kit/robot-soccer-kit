// Recording settings (settings panel)

function recorder_initialize(backend) {
    // The switches reflect the backend settings (e.g. after the page is reloaded)
    function update() {
        backend.get_recording_settings(function (settings) {
            $('#activate-rec').prop('checked', settings.ready_to_record);
            $('#record-commands').prop('checked', settings.record_commands);
            $('.display-rec-settings').toggleClass('d-none', !settings.ready_to_record);
        });
    }
    update();
    $('#settings-panel').on('show.bs.offcanvas', update);

    $('#activate-rec').change(function () {
        backend.set_ready_to_record($(this).is(':checked'), update);
    });

    $('#record-commands').change(function () {
        backend.set_record_commands($(this).is(':checked'), update);
    });
}
