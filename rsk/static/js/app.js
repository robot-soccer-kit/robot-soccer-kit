// Entry point of the interface: backend connection, modes, tabs and theme

// Calls to the backend API: backend.method(arg1, arg2, ..., callback)
class APIBackend {
    constructor(url) {
        let lastErrors = {};

        return new Proxy(this, {
            get: function get(target, name) {
                return function (...args) {
                    let callback = null;
                    if (args.length && typeof (args[args.length - 1]) == 'function') {
                        callback = args.pop();
                    }

                    // Some commands take time on the backend (cameras listing, robots identification)
                    let timeout = { cameras: 10000, identify: 60000 }[name] || 3000;
                    $.get({
                        url: url,
                        data: { command: name, args: JSON.stringify(args) },
                        timeout: timeout,
                        success: function (result) {
                            $('body').removeClass('backend-lost');
                            if (!result) {
                                return;
                            }
                            if (result[0]) {
                                if (callback) {
                                    callback(result[1]);
                                }
                            } else {
                                // The same error is not shown again and again (e.g. polling)
                                let message = String(result[1]);
                                console.log('Error (' + name + '): ' + message);
                                if (!lastErrors[message] || Date.now() - lastErrors[message] > 5000) {
                                    lastErrors[message] = Date.now();
                                    notify(message, 'danger');
                                }
                            }
                        },
                    }).fail(function () {
                        $('body').addClass('backend-lost');
                    });
                };
            }
        });
    }
}

// Current tab (used by modules to only refresh what is visible)
var current_tab = null;

function setTab(page) {
    // Unknown tab, or tab not available in this mode (e.g. Vision in simulation)
    let tab = $('.nav-tab[rel="' + page + '"]')[0];
    if (!$('.page-' + page).length || !tab || getComputedStyle(tab).display == 'none') {
        page = 'referee';
    }
    current_tab = page;
    document.body.dataset.tab = page;

    $('.page').hide();
    $('.page-' + page).show();
    $('.nav-tab .nav-link').removeClass('active').removeAttr('aria-current');
    $('.nav-tab[rel="' + page + '"] .nav-link').addClass('active').attr('aria-current', 'page');
    $(document).trigger('rsk:tab', [page]);

    // Closing the menu on small screens (Bootstrap ignores hide() while the menu is opening: a
    // quick tap on a tab, so it is closed once opened)
    let menu = document.getElementById('main-nav');
    let collapse = bootstrap.Collapse.getInstance(menu);
    if (collapse) {
        if (menu.classList.contains('collapsing')) {
            menu.addEventListener('shown.bs.collapse', () => collapse.hide(), { once: true });
        } else {
            collapse.hide();
        }
    }
}

function initializeTabs() {
    $('.nav-tab, .goto-tab').click(function (event) {
        event.preventDefault();
        let page = $(this).attr('rel');
        history.replaceState(null, '', '#' + page);
        setTab(page);
    });

    let page = window.location.hash.replace('#', '');
    setTab(page || 'referee');
}

function initializeTheme() {
    function apply(theme) {
        document.documentElement.setAttribute('data-bs-theme', theme);
        $('.theme-toggle i')
            .toggleClass('bi-moon-stars', theme == 'light')
            .toggleClass('bi-sun', theme == 'dark');
        $(document).trigger('rsk:theme', [theme]);
    }

    apply(document.documentElement.getAttribute('data-bs-theme') || 'light');

    $('.theme-toggle').click(function () {
        let theme = document.documentElement.getAttribute('data-bs-theme') == 'dark' ? 'light' : 'dark';
        try {
            localStorage.setItem('rsk-theme', theme);
        } catch (e) { }
        apply(theme);
    });
}

$(document).ready(function () {
    let backend = new APIBackend('http://' + document.location.host + '/api');
    initializeTheme();

    // All the modes are known before the tabs are initialized (a tab can be the one of a mode)
    backend.replay_mode_file(function (replayFile) {
        backend.is_simulated(function (simulated) {
            backend.is_competition(function (competition) {
                backend.scheduler_url(function (schedulerUrl) {
                    backend.constants(function (constants) {
                        let mode = replayFile !== '' ? 'replay' : (simulated ? 'simulation' : 'real');
                        $('body').addClass('mode-' + mode);
                        if (competition) {
                            $('body').addClass('mode-competition');
                        }
                        if (schedulerUrl) {
                            $('body').addClass('mode-scheduler');
                        }
                        initializeTabs();

                        if (mode == 'replay') {
                            replay_initialize(backend, constants);
                        } else {
                            referee_initialize(backend, constants);
                            simulator_initialize(backend, constants, mode == 'simulation');
                            control_initialize(backend);
                            recorder_initialize(backend);
                            if (mode == 'real') {
                                video_initialize(backend);
                                robots_initialize(backend);
                            }
                        }
                        if (competition) {
                            competition_initialize(backend);
                        }
                        if (schedulerUrl) {
                            scheduler_initialize(backend, schedulerUrl);
                        }
                    });
                });
            });
        });
    });
});
