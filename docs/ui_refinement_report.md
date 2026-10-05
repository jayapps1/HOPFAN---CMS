# HOPFAN member form, dropdown and login refinement

Implemented 5 October 2026 against the existing application. Attendance services, authentication services, database models and migrations are unchanged.

## 1. Files changed

New components:

- `src/ui/components/modern_select.py`
- `src/ui/components/multi_select_dropdown.py`
- `src/ui/components/select_popup.py`
- `src/ui/components/icon_entry.py`
- `src/ui/login/brand_panel.py`

Updated UI: `src/ui/components/modern.py`, `date_picker.py`, `totp_input.py`, `src/ui/icons.py`, `src/ui/theme.py`, `src/ui/login/login_view.py` and `src/ui/members/member_form_dialog.py`.

Verification: added `tests/test_ui_refinement.py` and two PostgreSQL cases in `tests/test_attendance.py`. This report, the link in `attendance_upgrade_report.md` and representative synthetic screenshots document the result.

## 2. Reusable components

`ModernSelect` supplies a 46px input with an 11px radius, adaptive border, image chevron, focus/hover and disabled states, a bound variable and the existing `get`, `set`, `configure` and selection-command API. Programmatic `set` does not invoke the user-selection command.

`MultiSelectDropdown` stores distinct IDs, supports preselection, selection/removal, search and a compact summary. Placeholder and search labels are configurable for reuse. `SelectPopup` supplies checked clickable rows, a bounded scrolling menu, search, Up/Down navigation, Enter/Space selection, Escape/outside-click closing and restoration of the previous modal grab. No dynamically created checkboxes are used. Popup timers and variable traces are removed on close.

`IconEntry` provides a 48px input with a 12px radius, a leading image icon, a visible placeholder for a bound variable, focus styling and an optional trailing action. `BrandPanel` keeps the official login identity separate from authentication UI.

## 3. Baptism behavior

- A new member starts Not baptized, with an empty disabled date and disabled Calendar button.
- Switching on immediately enables both controls. Dates display as DD/MM/YYYY and submit in ISO date form.
- Switching off clears the form variable, disables typing and Calendar, closes any open calendar, and submits `baptized=False, baptism_date=None`.
- Edit loads a baptized member's existing date. A member marked not baptized starts with an empty disabled field, even if its input dictionary contains a stale date.
- The existing `MemberService._apply_fields` already forces the database date to NULL when not baptized. It was retained and verified directly against PostgreSQL, including an invalid stale date while off.

The form now has Profile, Personal information, Contact information, Church information and Ministry participation headings. Save/Cancel remain in the fixed footer. Existing photo-save retry behavior remains intact.

## 4. Ministry multi-select

The stack of large ministry buttons is replaced with one searchable field. Selections show checked rows while open and a name/count summary while closed, with selected names beneath it. Existing IDs are preselected and duplicate IDs collapse to one selection. Clicking a selected row removes it. Search does not discard selections.

Saving retains the original primary ministry order when that ministry remains selected. The existing service handles relationship updates; the many-to-many model is unchanged. PostgreSQL checks verify three active relationships, deduplication, additions/removals and retention of existing relationship IDs.

## 5. Dropdown audit and replacements

Existing `ModernComboBox` imports now resolve to `ModernSelect`, so ordinary selectors share the new component without changing page behavior.

| Area | Ordinary controls using ModernSelect |
| --- | --- |
| Add/Edit Member | Gender, marital status, membership status |
| Member directory | Status filter |
| Attendance directory | State, type and authorized ministry filters |
| Attendance roster | Ministry and attendance-status filters where permitted |
| Attendance creation | Type, scope, ministry, initial state and advanced roster selection |
| Attendance correction | Corrected status |
| Administration/access dialog | User and ministry selection |
| Calendar | Month selection |

The calendar year remains directly editable in a styled 46px entry; a readonly replacement would remove useful birth-year typing. Login retains its segmented authentication-mode control. Dashboard cards, current ministry summaries and planned workspaces have no additional ordinary dropdowns to replace. No future finance/report logic was invented.

## 6. Login redesign

The navy brand panel shows the official logo, HOPFAN, the full church name, Church Management System and supporting text. The clean sign-in surface uses a 30px welcome heading, visible labels, segmented Password/Authenticator modes, the `name@example.com` placeholder, a lock icon and an eye/eye-off action inside the password input. Content height follows the form, with DPI-aware width and a neatly placed theme switch.

Password and authenticator remain alternative service calls. Enter submits password sign-in. Six equal authenticator boxes retain forward movement, Backspace navigation, six-digit paste and verification after digit six. Pending verification is cancelled when boxes are cleared or destroyed during a mode change. Authentication still runs through the existing background loader and success callback.

Missing input, authentication errors and locked-account messages are inline. Dark-mode links and errors use readable adaptive colors. No window-alpha transition was introduced.

## 7. Light/dark verification

Desktop checks exercised login in both modes at viewports representing 1366x768, 1600x900 and 1920x1080, allowing for Windows chrome. Member editing, enabled/disabled dates, multi-select, single-select and popup handling were checked in both themes. Existing attendance/dashboard screens and fixed footers passed their three-size, two-theme suite.

These checks use the installed Windows DPI and simulated client viewports; they do not change physical monitor settings. Manual screenshot review checked spacing, text, selected states, disabled states and controls staying visible.

Representative screenshots contain synthetic data:

- [Password login, light](screenshots/login_password_1366_light.png)
- [Password login, 1920 dark viewport](screenshots/ui_refinement/login_password_1920_dark.png)
- [Authenticator login, dark](screenshots/ui_refinement/login_totp_1366_dark.png)
- [Member baptism off, light](screenshots/ui_refinement/member_light_off.png)
- [Member baptism on, dark](screenshots/ui_refinement/member_dark_on.png)
- [Ministry popup, light](screenshots/ui_refinement/ministries_light.png)
- [Ministry popup, dark](screenshots/ui_refinement/ministries_dark.png)
- [Single-select popup, light](screenshots/ui_refinement/single_light.png)
- [Single-select popup, dark](screenshots/ui_refinement/single_dark.png)

## 8. Tests performed

36 distinct checks passed: 22 isolated PostgreSQL tests, 3 idle-session tests, 7 existing desktop tests and 4 new desktop refinement tests. Relevant interaction tests were repeated after the DPI, contrast and lifecycle corrections.

The new desktop cases cover baptism off/on/off payloads, date selection, closing an opening calendar, both edit states, three ministry selections, deselection, search, existing IDs, fixed footers, keyboard navigation, popup bounds/width, outside click, Escape, modal-grab restoration, repeated popup opening/closing, destroying an owner with an open popup, disabled selects, login validation/locked state, password visibility, TOTP digit-six timing, paste, Backspace and cancellation on mode change. GUI authentication uses mocked services; no production credentials were used.

```powershell
.venv\Scripts\python.exe -m compileall -q src tests
.venv\Scripts\python.exe -m unittest tests.test_attendance tests.test_session -v
.venv\Scripts\python.exe -m unittest tests.test_ui_smoke -v
.venv\Scripts\python.exe -m unittest tests.test_ui_refinement -v
git diff --check
```

PostgreSQL tests create and remove their private schema. A read-only comparison confirmed all original rows still match `backups/attendance_before_snapshot.json` on their original columns: 1 member, 14 ministries, 1 user, 1 original attendance session and 1 attendance record. The current database also has one additional attendance session, retained without modification. No test schemas remain. Alembic is still at `c603420e8020`; no migration was added or run for this task.

## 9. Remaining UI inconsistencies and limits

No remaining regression was found in the requested member, login or select workflows. Compact entry/date controls elsewhere retain their existing heights; ordinary select controls use the new 46px style. Native file selection and window chrome remain OS controls. Future module selectors should use these shared components when those services are implemented.

Visual checks were performed on the available Windows desktop and DPI. Other operating systems and monitor/DPI combinations were not tested.
