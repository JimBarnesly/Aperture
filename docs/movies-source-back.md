# Movies source-directory Back: native history collision

## Evidence

Run `42820458960`, head `ea3276a6c4810e849450db0e28fb84f7431d7991`,
artifact `aperture-movies-online-ea3276a6c4810e849450db0e28fb84f7431d7991`
(id `13766731344`) fails `home-source-directory-cancel`, window10000 not11120.
Retained Kodi log:

- Local fallback Back at13:00:50.221 and13:00:54.018 correctly returns11120.
- Search/browser Videos is active before13:02:27.302, when Movies home opens.
-13:02:30.999: row action carries `id=tt1234567&resume=1`.
-13:02:31.360: Videos opens; correct nonmodal source directory completes.
-13:02:33.485: actual PreviousWindow, then13:02:33.801 Home.xml initializes.
  This is not an ignored Back, closing keyboard, failed lookup or timeout issue.

Kodi21.3 `CGUIWindowManager::AddToWindowHistory` truncates the stack when the
new window ID already exists. The failing sequence is
`[10000,10025] -> [10000,10025,11120] -> [10000,10025] -> [10000]`.
`ActivateWindow(Videos,...,return)` only sets the media start directory in
`CGUIMediaWindow`; it does not pin the caller as the previous window. This
explains why the initial local fallback works and the later source return fails.

Pinned references:
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIWindowManager.cpp
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/windows/GUIMediaWindow.cpp
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIWindow.cpp
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIControlGroup.cpp
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIControl.cpp

## Fix

Home source buttons and home details mark only their source entry URL `home=1`.
The marker is local navigation data: provider lookup still receives only IMDb ID;
source picking retains ID/source/resume and does not propagate the marker.
The existing native directory remains nonmodal, with no select/progress dialog.

Both skin assembly paths patch inherited interactive view/menu controls with a
conditional Back action. It applies only in Videos, this add-on, the marked
source entry, and with no visible modal. Ordinary Search, browsing, source
selection outside home, Music/Games and dialogs retain their original actions.
The return handler rechecks origin path/window/abort before `ReplaceWindow(1120)`.
Replace removes Videos rather than introducing a home/source Back cycle. Home
control state is restored by Kodi; no reset, re-selection or forced resume.

Two native details matter: groups cannot handle Back (`OnAction` returns false),
and an action-only `onback` can fall through `OnMove` into native PreviousWindow.
The shipped implementation is on interactive controls and has a conditional
numeric target9000, consuming the key in the existing native menu while the
origin-guarded script runs. No timers, global keymap, poller, permanent previous
window override or home-onload redirect. A group-only prototype was rejected
against upstream source and removed before final verification.

The Pythonless installer retains its existing limited fallback, now explicitly
warning source-return integration is unavailable and directing to the full ZIP.
Complete ZIP and Python-enabled source installation contain the fix.

## Verification and gate

- Regression first reproduces10000 versus11120 with prior Videos history,
  resume0/1 and home details; fresh-history control already passes. Then GREEN.
- Both-install-path test observed RED before wiring the patcher, then GREEN.
- Six focused regressions cover route/history, normal Search/source Back,
  no return loops, stale/abort/window guards, patch idempotence and original
  actions. Existing provider test verifies marker never reaches lookup/pick.
- Native acceptance is strengthened with restored source-button focus,
  row identity and explicit resume assertions. Original11120 expected return,
  immediate playback Back, timeouts, and nonmodal/no-resolution checks retained.
- Full offline suite:886 passed in loopback-only unprivileged namespace.
- Complete skin/Movies ZIP assembly passed. Source XML checksums unchanged;
  inherited XML transformation is applied after copy in both builders.
- Native exact-head CI is **pending**: Xvfb, pulseaudio and pactl absent locally.
  No live Kodi, profile, account, display, deployment or push operations.

Requires matching skin + Movies. Rollback base `ea3276a`; parent owns review,
push and exact-head CI. Do not lift the native gate based on the offline model.
