#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Browse NONPLAYABLE synthetic Games in the already ZIP-tested private profile.

Only this module's guarded Home/system-folder activations can send Return to a
media window. Dummy game rows are enumerated/focused, NEVER activated or played.
Kodi settings are edited only while its disposable process is stopped, and the
original file bytes/existence are restored even after an assertion failure.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

from game_browse_smoke_fixture import prepare

ADDON_ID = "plugin.games.apeture"
GAMES_WINDOW = 10821
NO_DIALOG = 9999
# Omega xbmc/guilib/WindowIDs.h: 10101 is progress; OK is 12002.
OK_DIALOG = 12002
EXPECTED_ERROR = "Apeture: operation failed (ScanError)"


def require_stopped(driver):
    process = driver.process
    if process is not None and process.poll() is None:
        raise AssertionError("Refusing a profile-file edit while disposable Kodi is running")


class SettingsSnapshot:
    """Own only one setting file in the exact fresh-ZIP disposable profile."""

    def __init__(self, driver, runtime):
        require_stopped(driver)
        runtime = Path(runtime).resolve()
        target = Path(driver.target)
        if (not runtime.name.startswith("apeture-kodi-smoke.") or target.is_symlink()
                or target.resolve() != runtime / "fresh-zip"):
            raise ValueError("Not the proven fresh-ZIP disposable profile")
        self.driver = driver
        self.target = target
        self.path = target / "data/userdata/addon_data" / ADDON_ID / "settings.xml"
        self.ensure_safe_path()
        if not (target / "data/userdata/guisettings.xml").is_file():
            raise ValueError("Fresh-ZIP profile marker is missing")
        self.original = self.path.read_bytes() if self.path.exists() else None
        self.created_directories = [parent for parent in (self.path.parent, self.path.parent.parent)
                                    if not parent.exists()]
        root = ET.fromstring(self.original) if self.original is not None else ET.Element("settings", version="2")
        if root.tag != "settings":
            raise ValueError("Unexpected add-on settings document")
        existing = root.findall("./setting[@id='rom_root']")
        if len(existing) > 1 or any((node.text or "").strip() for node in existing):
            raise ValueError("Browse test requires the proven unconfigured fresh profile")

    def ensure_safe_path(self):
        for path in (self.target, self.target / "data", self.target / "data/userdata",
                     self.path.parent.parent, self.path.parent, self.path):
            if path.is_symlink() or not path.resolve().is_relative_to(self.target.resolve()):
                raise ValueError("Unsafe disposable profile path")

    def set_root(self, value):
        require_stopped(self.driver)
        self.ensure_safe_path()
        root = ET.fromstring(self.original) if self.original is not None else ET.Element("settings", version="2")
        setting = root.find("./setting[@id='rom_root']")
        if setting is None:
            setting = ET.SubElement(root, "setting", id="rom_root")
        setting.attrib.pop("default", None)
        setting.text = str(value)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(root).write(self.path, encoding="utf-8", xml_declaration=True)

    def restore(self):
        require_stopped(self.driver)
        self.ensure_safe_path()
        if self.original is None:
            self.path.unlink(missing_ok=True)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(self.original)
        for directory in self.created_directories:
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()

    def is_restored(self):
        return (not self.path.exists()) if self.original is None else self.path.read_bytes() == self.original


def no_game(state):
    if state.get("game_playing") is not False:
        raise AssertionError("Game playback must remain false; a missing observer value is not a pass")


def item_signature(state):
    return (state.get("list_item"), state.get("item_path"), state.get("item_is_parent"))


def settled(driver):
    """Wait for consecutive fresh observer frames, not stale queued key state."""
    previous, since, frames, last_sequence = None, 0, 0, -1

    def stable(state):
        nonlocal previous, since, frames, last_sequence
        no_game(state)
        signature = (state.get("window"), state.get("dialog"), state.get("focus"),
                     state.get("directory"), *item_signature(state))
        if signature != previous:
            previous, since, frames, last_sequence = signature, state["time"], 0, -1
        if state["sequence"] != last_sequence:
            frames += 1
            last_sequence = state["sequence"]
        return frames >= 3 and state["time"] - since >= 0.5

    return driver.wait("browse-only focused row settled", stable, timeout=8)


def plugin_query(path):
    parsed = urlsplit(path or "")
    if parsed.scheme != "plugin" or parsed.netloc != ADDON_ID or parsed.path not in ("", "/"):
        raise AssertionError("Focused row is not an exact Games companion route")
    query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=8)
    if any(len(values) != 1 for values in query.values()):
        raise AssertionError("Ambiguous duplicate route parameter")
    return {key: values[0] for key, values in query.items()}


def require_system_activation(state, expected):
    no_game(state)
    query = plugin_query(state.get("item_path"))
    if not (state.get("window") == GAMES_WINDOW and state.get("dialog") == NO_DIALOG
            and state.get("focus") == 50 and state.get("directory") == "root"
            and state.get("item_is_folder") is True and state.get("item_is_parent") is False
            and state.get("list_item") == expected["label"]
            and state.get("item_system") == expected["id"]
            and query == {"action": "system", "system": expected["id"]}):
        raise AssertionError("Refusing Return: focus is not the exact expected system folder")


def open_games(driver):
    driver.focus_home(9100)
    state = settled(driver)
    if state.get("window") != 10000 or state.get("dialog") != NO_DIALOG or state.get("focus") != 9100:
        raise AssertionError("Refusing Return outside the installed Home Games button")
    driver.key("Return")


def directory_state(driver, directory, state="ready"):
    current = driver.wait("Games {} / {}".format(directory, state),
        lambda value: value.get("window") == GAMES_WINDOW and value.get("dialog") == NO_DIALOG
        and value.get("library_state") == state and value.get("directory") == directory)
    no_game(current)
    return settled(driver)


def list_rows(driver, maximum=12):
    """Walk a complete bounded native list cycle using Down only; never select."""
    first = settled(driver)
    if first.get("window") != GAMES_WINDOW or first.get("dialog") != NO_DIALOG or first.get("focus") != 50:
        raise AssertionError("Browse enumeration requires the native Games list")
    rows, signatures = [], set()
    state = first
    while True:
        no_game(state)
        signature = item_signature(state)
        if signature in signatures:
            if signature != item_signature(first):
                raise AssertionError("Native list looped before returning to its first row")
            return rows
        signatures.add(signature)
        rows.append(dict(state))
        if len(rows) > maximum:
            raise AssertionError("Unexpected extra rows in the bounded browse fixture")
        before = driver.key("Down")
        driver.wait("native Games row changed after Down",
                    lambda value: item_signature(value) != signature, after=before, timeout=5)
        state = settled(driver)
        if state.get("focus") != 50 or state.get("dialog") != NO_DIALOG:
            raise AssertionError("Focus left the native list during browse enumeration")


def assert_root_rows(rows, expected):
    systems, actions, parents = {}, [], 0
    for row in rows:
        no_game(row)
        if row.get("item_is_parent"):
            parents += 1
            continue
        query = plugin_query(row.get("item_path"))
        if query.get("action") == "system":
            identifier = query.get("system")
            if identifier in systems or row.get("item_is_folder") is not True:
                raise AssertionError("Duplicate or non-folder system row")
            systems[identifier] = row
        elif query in ({"action": "settings"}, {"action": "help"}):
            actions.append(query["action"])
        else:
            raise AssertionError("Unexpected root item (including a game row at root)")
    if set(systems) != {system["id"] for system in expected["systems"]}:
        raise AssertionError("Unknown/empty system leaked into the real root list")
    if sorted(actions) != ["help", "settings"] or parents > 1:
        raise AssertionError("Unexpected root management/parent rows")
    for system in expected["systems"]:
        actual = systems[system["id"]]
        if (actual.get("list_item") != system["label"] or actual.get("item_system") != system["id"]
                or actual.get("item_game_count") != str(system["game_count"])):
            raise AssertionError("Visible system label/count differs from the synthetic fixture")


def assert_game_rows(rows, system):
    titles, actions, parents = [], [], 0
    for row in rows:
        no_game(row)
        if row.get("item_is_parent"):
            parents += 1
            continue
        query = plugin_query(row.get("item_path"))
        if query.get("action") == "play":
            if row.get("item_is_folder") is not False or query.get("system") != system["id"]:
                raise AssertionError("Unexpected playable-row routing")
            titles.append(row.get("list_item"))
        elif query in ({"action": "settings"}, {"action": "help"}):
            actions.append(query["action"])
        else:
            raise AssertionError("Unexpected system-list item")
    if sorted(titles) != sorted(game["title"] for game in system["games"]):
        raise AssertionError("Actual game titles differ; unsupported content may have leaked")
    if sorted(actions) != ["help", "settings"] or parents > 1:
        raise AssertionError("Unexpected system management/parent rows")


def check_session_logs(driver, sessions, unavailable_session):
    """One exact expected error, in one intentional failure session only."""
    expected = []
    for session in sessions:
        relative = "logs/session-{}.log".format(session)
        log = (Path(driver.out) / relative).read_text(encoding="utf-8", errors="replace")
        for marker in ("Error loading skin", "failed to load skin", "EXCEPTION Thrown (PythonToCppException)"):
            if marker.lower() in log.lower():
                raise AssertionError("Game browse runtime error: " + marker)
        failures = [line for line in log.splitlines() if "Apeture: operation failed" in line]
        if session == unavailable_session:
            if len(failures) != 1 or EXPECTED_ERROR not in failures[0]:
                raise AssertionError("Unavailable-root phase did not produce exactly its expected ScanError")
            expected.append({"session": session, "log": relative, "marker": EXPECTED_ERROR, "count": 1})
        elif failures:
            raise AssertionError("Unexpected operation failure outside unavailable-root phase")
    return expected


def run(driver, runtime):
    """Called only after successful fresh-ZIP acceptance has stopped Kodi."""
    require_stopped(driver)
    snapshot = SettingsSnapshot(driver, runtime)
    manifest = prepare(Path(runtime))
    expected = manifest["expected"]
    first_check = len(driver.checks)
    sessions, unavailable_session = [], None
    try:
        snapshot.set_root(manifest["root"])
        driver.start("skin.apeture")
        sessions.append(driver.session)
        open_games(driver)
        state = directory_state(driver, "root")
        if state.get("game_count") != "3" or state.get("system_count") != "2":
            raise AssertionError("Actual root summary includes wrong game/system counts")
        assert_root_rows(list_rows(driver), expected)
        driver.capture("games-01-synthetic-systems")
        for system in expected["systems"]:
            driver.find(system["label"], steps=8)
            require_system_activation(settled(driver), system)
            driver.key("Return")  # Guard above permits ONLY this exact folder.
            state = directory_state(driver, "system")
            if state.get("game_count") != str(system["game_count"]) or state.get("system_count") != "1":
                raise AssertionError("Actual system summary has wrong counts")
            assert_game_rows(list_rows(driver), system)
            driver.find(system["games"][0]["title"], steps=8)
            focused = settled(driver)
            if focused.get("item_is_folder") is not False or focused.get("list_item") != system["games"][0]["title"]:
                raise AssertionError("Expected dummy game is not visibly focused")
            driver.capture("games-02-synthetic-" + system["id"] + "-never-played")
            # Omega maps BackSpace to Back; Escape is PreviousMenu and can
            # leave the Games window rather than return one folder level.
            driver.key("BackSpace")
            directory_state(driver, "root")
            assert_root_rows(list_rows(driver), expected)
        driver.capture("games-03-back-to-systems")
        driver.stop()

        snapshot.set_root(manifest["unavailable_root"])
        driver.start("skin.apeture")
        sessions.append(driver.session)
        unavailable_session = driver.session
        open_games(driver)
        driver.wait("expected missing-root OK dialog", lambda value: value.get("dialog") == OK_DIALOG)
        state = settled(driver)
        if state.get("dialog") != OK_DIALOG:
            raise AssertionError("Refusing Return without the expected read-error OK dialog")
        driver.capture("games-04-unavailable-root-dialog")
        driver.key("Return")  # ACK guarded native OK modal only, never a game.
        directory_state(driver, "root", "error")
        driver.find("Configure ROM folder…", steps=5)
        recovery = settled(driver)
        if plugin_query(recovery.get("item_path")) != {"action": "settings"}:
            raise AssertionError("Unavailable collection lacks the real settings recovery action")
        driver.capture("games-05-unavailable-root-recovery")
        driver.stop()

        snapshot.restore()
        driver.start("skin.apeture")
        sessions.append(driver.session)
        open_games(driver)
        directory_state(driver, "root", "unconfigured")
        driver.capture("games-06-restored-unconfigured")
        driver.key("Escape")
        final = driver.wait("Home after restored Games", lambda value: value.get("window") == 10000
                            and value.get("dialog") == NO_DIALOG)
        no_game(final)
        driver.stop()
        expected_errors = check_session_logs(driver, sessions, unavailable_session)
    finally:
        # Always stop first, including on failed focus assertions. If shutdown
        # failed but killed the child, require_stopped still prevents a live edit.
        try:
            driver.stop()
        finally:
            snapshot.restore()
    if not snapshot.is_restored():
        raise AssertionError("Exact original setting bytes/existence were not restored")
    return {"status": "passed", "label": manifest["label"], "never_launched": True,
            "scope": "Synthetic NONPLAYABLE native game browsing, filtering, Back and missing-root recovery only",
            "checks": driver.checks[first_check:], "fixture": manifest,
            "original_settings_restored_exactly": True, "final_library_state": "unconfigured",
            "sessions": sessions, "expected_errors": expected_errors,
            "limitations": ["Dummy files are deliberately invalid, not ROMs",
                            "No emulator/core launch, gamepad, Pi or game compatibility acceptance"]}
