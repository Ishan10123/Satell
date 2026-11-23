# Conversation menu fix

## Root cause

Each action menu was a native `<details>` panel positioned absolutely beneath a trigger within the sidebar's scrolling/overflowing ancestor. That made it subject to sidebar clipping. On small screens, CSS changed the panel to `position: fixed` with a hard-coded right offset and removed its reliable relationship to the trigger. Native details instances also had no shared state, outside-click handler, or document-level Escape behavior, so several could stay open.

## Fix

`chat/static/chat/app.js` now manages conversation and account menus through a shared `data-dropdown-trigger` / `data-dropdown-panel` contract. It portals an opened panel to `document.body`, measures it, chooses above/below placement based on available viewport space, clamps horizontal and vertical bounds, and applies a bounded scroll area. A single active-menu reference ensures only one menu is open. Outside click, Escape, focus leaving, selection, page/sidebar scroll, and resize close it. Arrow keys, Home/End, ARIA `aria-haspopup`, `aria-expanded`, `role=menu`, and `role=menuitem` are included.

## Verification

Rendered markup/ARIA and controller behavior contracts are covered by Django tests. The browser-control skill file was missing and no browser automation surface was available, so actual desktop/mobile clicks, visual clipping inspection, and screenshots are **NOT_TESTED**. Use the steps in the manual verification checklist in `phase6c_remaining_limitations.md` after the candidate is built and running.
