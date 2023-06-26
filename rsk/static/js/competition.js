function competition_initialize(backend) {
    let teams = {};

    let data = localStorage.getItem("teams")
    if (data != null) {
        try {
            teams = JSON.parse(data);
        } catch (SyntaxError) {
            teams = {}
        }
    }

    function setTeam(name, color) {
        $(".team-name[rel=" + color + "]").val(name)
        $(".key-" + color).val(teams[name]);
        $(".key-" + color).change();
    }

    function renderTeams() {
        console.log(teams);
        let html = '';
        for (let name in teams) {
            html += "<tr>"
            html += "  <td>" + name + "</td>"
            html += '  <td>'
            html += '<a class="m-2 btn btn-primary team-blue" rel="' + name + '" href="#">Blue</a>'
            html += '<a class="m-2 btn btn-success team-green" rel="' + name + '" href="#">Green</a>'
            html += '<a class="m-2 btn btn-danger team-remove"  rel="' + name + '" href="#">Remove</a>'
            html += '</td>'
            html += "</tr>"
        }
        $('.competition-teams').html(html);


        $('.team-blue').click(function () {
            let name = $(this).attr('rel');
            setTeam(name, "blue");
        });
        $('.team-green').click(function () {
            let name = $(this).attr('rel');
            setTeam(name, "green");
        });
        $('.team-remove').click(function () {
            let name = $(this).attr('rel');
            delete (teams[name]);
            renderTeams();
        });
    }

    $('.add-team').click(function () {
        teams[$('.add-team-name').val()] = $('.add-team-password').val();
        localStorage.setItem("teams", JSON.stringify(teams));
        renderTeams();
    });

    renderTeams();
}