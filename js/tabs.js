$(document).ready(function() {
    function setTab(page) {
        $('.page').hide();
        $('.page-'+page).show();
        $('.nav-item a').removeClass('active');
        $('.nav-item[rel="'+page+'"] a').addClass('active');
    }

    $('.nav-item').click(function() {
        setTab($(this).attr('rel'));
    });

    setTab('vision');
});