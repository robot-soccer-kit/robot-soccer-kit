function recorder_initialize(backend) {

    $('#activate-rec').change(function() {

        if ($(this).is(":checked")) {
            $(".display-rec-settings").removeClass("d-none")

            backend.set_ready_to_record(true)
        } else {
            $(".display-rec-settings").addClass("d-none")
            backend.set_ready_to_record(false)
        }
    })

    $('.display-rec-settings input').click(function () {
        const rel = $(this).attr('rel')
        const checked = $(this).is(':checked')

        if (rel === "rec-commands") {
            if (checked) {
                backend.set_record_commands(true)
            } else {
                backend.set_record_commands(false)
            }

        } else if (rel === "rec-detection") {
            if (checked) {
                backend.set_record_detection(true)
            } else {
                backend.set_record_detection(false)
            }
        }
    });

}