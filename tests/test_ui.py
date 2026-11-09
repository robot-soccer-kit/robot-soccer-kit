"""
Tests of the Game Controller interface, in a headless browser (Playwright). The interface is served
by the simulated backend shared by the tests.

The browser is Chrome if installed, else the Chromium of Playwright (playwright install chromium).
The tests are skipped if no browser is available.
"""

import logging
import re
import threading

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from rsk import client, game_controller  # noqa: E402

SIZES = [(1920, 1080), (1366, 650), (1024, 640)]

# Elements cut by the bottom or the right of the window, outside the panels that scroll on purpose
CUT_ELEMENTS = """() => {
    const page = [...document.querySelectorAll('.page')].find(p => getComputedStyle(p).display != 'none');
    const cut = [];
    for (const element of page.querySelectorAll('*')) {
        const rect = element.getBoundingClientRect();
        if (!rect.width || !rect.height || getComputedStyle(element).visibility == 'hidden') continue;
        if (rect.bottom <= innerHeight + 1 && rect.right <= innerWidth + 1) continue;
        let parent = element.parentElement, scrolls = false;
        while (parent && parent != page.parentElement) {
            const overflow = getComputedStyle(parent).overflowY;
            if ((overflow == 'auto' || overflow == 'scroll') && parent.scrollHeight > parent.clientHeight) {
                scrolls = true;
                break;
            }
            parent = parent.parentElement;
        }
        if (!scrolls) cut.push(String(element.className || element.tagName));
    }
    return cut;
}"""

VISIBLE_TABS = """() => [...document.querySelectorAll('.nav-tab')]
    .filter(tab => getComputedStyle(tab).display != 'none')
    .map(tab => tab.getAttribute('rel'))"""


def serve(app):
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}/"


@pytest.fixture(scope="module")
def server(backend):
    server, url = serve(game_controller.create_app(backend))
    yield url
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = None
        for options in ({"channel": "chrome"}, {}):
            try:
                browser = playwright.chromium.launch(headless=True, **options)
                break
            except Exception:
                continue
        if browser is None:
            pytest.skip(
                "No browser for the interface tests (playwright install chromium)"
            )
        yield browser
        browser.close()


def reset(backend):
    """
    Leaves the shared backend as the tests found it
    """
    referee = backend.referee
    referee.stop_game()
    referee.reset_score()
    for team in ("green", "blue"):
        referee.set_team_name(team, "")
        referee.game_state["teams"][team]["x_positive"] = team == "green"
    backend.set_ready_to_record(False)
    backend.competition = False
    backend.control.remove_task("force-place")
    for team, number, (x, y, turn) in client.configurations["game_green_positive"]:
        backend.teleport(f"{team}{number}", x, y, turn)
    backend.teleport("ball", 0, 0, 0)


@pytest.fixture
def open_page(browser, server, backend):
    """
    Opens the interface, fails if the page has JavaScript errors
    """
    contexts, errors = [], []

    def open_page(size=(1600, 900), url=server, hash="referee", color_scheme="light"):
        context = browser.new_context(
            viewport={"width": size[0], "height": size[1]}, color_scheme=color_scheme
        )
        contexts.append(context)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: (
                errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.goto(url + "#" + hash)
        page.wait_for_function("document.body.className.includes('mode-')")
        return page

    yield open_page

    for context in contexts:
        context.close()
    reset(backend)
    assert errors == []


def tab(page, name):
    page.click(f".nav-tab[rel={name}] .nav-link")
    page.wait_for_timeout(400)


def test_simulation_tabs(open_page):
    page = open_page()

    assert page.evaluate(VISIBLE_TABS) == ["control", "referee"]
    expect(page.locator(".navbar .simulation-mode")).to_be_visible()
    expect(page.locator(".page-referee")).to_be_visible()
    # The simulated field is drawn
    page.wait_for_function("document.getElementById('back').width > 100")


@pytest.mark.parametrize("size", SIZES, ids=[f"{w}x{h}" for w, h in SIZES])
def test_no_scroll_and_nothing_cut(open_page, size):
    page = open_page(size)
    # Worst case of the referee page: a goal waiting for validation
    page.add_style_tag(content=".goal-pending { display: block !important; }")

    for name in page.evaluate(VISIBLE_TABS):
        tab(page, name)
        overflow = page.evaluate("document.documentElement.scrollHeight - innerHeight")
        assert overflow <= 0, f"{name} tab scrolls"
        assert page.evaluate(CUT_ELEMENTS) == [], f"{name} tab has cut elements"


def test_simulated_field_fits_its_area(open_page):
    page = open_page((1366, 650))
    page.wait_for_function("document.getElementById('back').width > 100")
    page.wait_for_timeout(300)

    field = page.locator("#back").bounding_box()
    area = page.locator(".field-view").bounding_box()
    canvas = page.evaluate(
        "[document.getElementById('back').width, document.getElementById('back').height]"
    )

    assert field["width"] <= area["width"] and field["height"] <= area["height"]
    # The field fills the area in one direction, and keeps its ratio
    assert max(field["width"] / area["width"], field["height"] / area["height"]) > 0.9
    assert field["width"] / field["height"] == pytest.approx(
        canvas[0] / canvas[1], rel=0.02
    )


def test_referee_game_flow(open_page, backend):
    page = open_page()
    simulator = backend.simulator
    # The ball is not at the center: the game waits for it to be placed
    simulator.objects["ball"].teleport(0.3, 0.3, 0)

    page.click(".start-game")
    expect(page.locator(".GameState")).to_have_text("Place the ball on the dot")
    expect(page.locator(".resume-game")).to_be_visible()

    # The game resumes when the ball is placed at the center
    simulator.objects["ball"].teleport(0, 0, 0)
    expect(page.locator(".game-state-pill")).to_have_class(
        re.compile("state-running"), timeout=5000
    )
    expect(page.locator(".pause-game")).to_be_visible()

    # Space bar: pause and resume
    page.keyboard.press("Space")
    expect(page.locator(".game-state-pill")).to_have_class(re.compile("state-paused"))
    page.keyboard.press("Space")
    expect(page.locator(".game-state-pill")).to_have_class(re.compile("state-running"))

    # Penalty
    page.click('.robot-penalty[rel="green1"] .penalize')
    expect(page.locator('.robot-penalty[rel="green1"] .robot-state')).to_contain_text(
        "Penalized by the referee"
    )
    page.click('.robot-penalty[rel="green1"] .unpenalize')
    expect(
        page.locator('.robot-penalty[rel="green1"] .robot-state')
    ).not_to_contain_text("Penalized")

    # Goal for blue, in the goal defended by green
    simulator.objects["green2"].teleport(0.5, 0.5, 0)
    simulator.objects["ball"].teleport(0.6, 0.2, 0)
    simulator.objects["ball"].velocity[:2] = [1.0, 0.0]
    expect(page.locator(".goal-pending")).to_be_visible(timeout=5000)
    expect(page.locator(".goal-pending-team")).to_have_text("Blue")
    expect(page.locator(".game-state-pill")).to_have_class(re.compile("state-goal"))
    expect(page.locator(".resume-game")).to_be_disabled()
    expect(page.locator('.team-block[data-team="blue"] .score')).to_have_text("1")

    page.click(".goal-pending .validate-goal")
    expect(page.locator(".goal-pending")).to_be_hidden()
    expect(page.locator("#RefereeHistory")).to_contain_text("Goal for Blue")
    expect(page.locator("#RefereeHistory")).to_contain_text("Validated")

    # The history is kept when the page is reloaded
    page.reload()
    expect(page.locator("#RefereeHistory")).to_contain_text("Validated")

    page.click(".stop-game")
    expect(page.locator(".start-game")).to_be_visible()


def test_teams_are_on_their_side(open_page, backend):
    page = open_page()

    def left_team():
        page.wait_for_timeout(400)
        blocks = {
            team: page.locator(
                f'.scoreboard .team-block[data-team="{team}"]'
            ).bounding_box()["x"]
            for team in ("green", "blue")
        }
        robots = {
            team: page.locator(f'.team-robots-col[data-team="{team}"]').bounding_box()[
                "x"
            ]
            for team in ("green", "blue")
        }
        assert min(blocks, key=blocks.get) == min(robots, key=robots.get)
        return min(blocks, key=blocks.get)

    # Green defends the positive x goal (right of the field)
    assert left_team() == "blue"
    backend.swap_team_sides()
    assert left_team() == "green"


def test_team_name(open_page, backend):
    page = open_page()

    page.fill('.team-name[rel="green"]', "Rhoban")
    page.keyboard.press("Tab")
    page.wait_for_timeout(500)

    assert backend.referee.game_state["teams"]["green"]["name"] == "Rhoban"


def test_theme_is_saved(open_page):
    page = open_page()
    assert page.get_attribute("html", "data-bs-theme") == "light"

    page.click(".theme-toggle")
    assert page.get_attribute("html", "data-bs-theme") == "dark"
    page.reload()
    page.wait_for_function("document.body.className.includes('mode-')")
    assert page.get_attribute("html", "data-bs-theme") == "dark"


def test_recording_settings(open_page, backend):
    page = open_page()

    page.click('button[data-bs-target="#settings-panel"]')
    page.locator("#activate-rec").check()
    page.wait_for_timeout(400)
    assert backend.get_recording_settings()["ready_to_record"]

    # The switch reflects the backend after a reload
    page.reload()
    page.click('button[data-bs-target="#settings-panel"]')
    expect(page.locator("#activate-rec")).to_be_checked()


def test_competition_teams(open_page, backend):
    backend.competition = True
    page = open_page(hash="competition")
    expect(page.locator(".page-competition")).to_be_visible()

    for name in ("Rhoban", "Bordeaux"):
        page.fill(".add-team-name", name)
        page.fill(".add-team-password", name.lower())
        page.click(".add-team")
    expect(page.locator(".competition-teams tr")).to_have_count(2)

    # Play as green: name and key are set
    page.click('.competition-teams tr[data-team="Rhoban"] .play-as[data-color="green"]')
    page.wait_for_timeout(500)
    assert backend.referee.game_state["teams"]["green"]["name"] == "Rhoban"
    assert backend.control.teams["green"]["key"] == "rhoban"
    backend.control.set_key("green", "")

    # Removing a team (confirmation dialog), still removed after a reload
    page.click('.competition-teams tr[data-team="Bordeaux"] .team-remove')
    page.click(".modal.show .confirm-button")
    expect(page.locator(".competition-teams tr")).to_have_count(1)
    page.reload()
    expect(page.locator('.competition-teams tr[data-team="Rhoban"]')).to_have_count(1)
    expect(page.locator('.competition-teams tr[data-team="Bordeaux"]')).to_have_count(0)


def test_replay(open_page, backend):
    # Recording a game with a validated goal
    simulator = backend.simulator
    backend.set_ready_to_record(True)
    backend.set_team_name("blue", "Bordeaux")
    backend.start_game()
    simulator.objects["ball"].teleport(0, 0, 0)
    page = open_page()
    expect(page.locator(".game-state-pill")).to_have_class(
        re.compile("state-running"), timeout=5000
    )
    simulator.objects["green2"].teleport(0.5, 0.5, 0)
    simulator.objects["ball"].teleport(0.6, 0.2, 0)
    simulator.objects["ball"].velocity[:2] = [1.0, 0.0]
    expect(page.locator(".goal-pending")).to_be_visible(timeout=5000)
    backend.validate_goal(True)
    page.wait_for_timeout(500)
    backend.stop_game()
    record = backend.get_record_filepath()
    assert record

    # Replaying it
    backend.replay = record
    try:
        server, url = serve(game_controller.create_app(backend))
        page = open_page(url=url)
        assert page.evaluate(VISIBLE_TABS) == ["referee"]
        expect(page.locator(".navbar .replay-mode")).to_be_visible()

        page.click(".start-replay-grp")
        expect(page.locator(".pause-replay")).to_be_visible()
        progress = page.locator(".replay-progress").bounding_box()
        page.mouse.click(
            progress["x"] + progress["width"] * 0.98,
            progress["y"] + progress["height"] / 2,
        )

        expect(page.locator("#RefereeHistory")).to_contain_text("Goal for Bordeaux")
        expect(page.locator("#RefereeHistory")).to_contain_text("Validated")
        expect(page.locator('.team-block[data-team="blue"] .score')).to_have_text("1")
        expect(page.locator('.team-name[rel="blue"]')).to_have_value("Bordeaux")
        server.shutdown()
    finally:
        backend.replay = ""
