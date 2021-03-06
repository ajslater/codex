# Codex News

## v0.6.7

- Dark admin pages and fix template overrides.

## v0.6.6

- Automate multi-arch builds

## v0.6.5

- Build Docker images for amd64 & arm64 manually.

## v0.6.4

- Fix reader bug that only displayed first page

## v0.6.3

- Add LOGLEVEL environment variable. Set to DEBUG to see everything.
- Removed DEV environment variable.
- Possible fix for newly imported covers not displaying.

## v0.6.2

- Librarian startup crash is intermittent and only in docker.
- Fixed DEBUG environment variable to be able to run in production.
- Added DEV environment variable for dev environment only.

## v0.6.1

- Fix librarian startup crash. Prevented admin actions from happening.

## v0.6.0

- Many new Filters
- New sort options: Updated Time and Maturity Rating
- New frontend URL scheme
- New API
- Added time to the browse card when sorting by time fields
- Fixed a bug importing Story Arc Series Groups and Genres. Requires re-import to correct.
- Fixed a bug with sorting that grouped improperly and showed the wrong covers for reverse sorts.
- Browser pagination footer now remains fixed on the page
- Browser pagination footer is now a slider to handle larger collecions
- Notifications now appear in reader as well as browser
- Scanning notifications on login not dissapearing bug squashed
- On comic import failure, log the path as well as the reason
- Fixed a bug where the browser settings menu wouldn't close when opening a dialog
- Codex version information moved to Browser > Settings

## v0.5.18

- Fix filters not changing display bug

## v0.5.17

- Fix root_path not parsing bug

## v0.5.16

- Fix broken startup when parsing json shared between front and back end

## v0.5.15

- Metadata popup is now 1000x+ faster.
- Metadata popup now shows created_at, updated_at and path (if admin).
- Removed numeric and common password validators. Made the minimum length 4.

## v0.5.14

- Metadata view for browse containers. Also observes filters.
- Fix scanning notification
- Fix unable to delete libraries bug
- Covers now regenerate on re-import.

## v0.5.13

- Admin Flag for automatically updating codex
- Force updates from the admin panel with an Admin Flag action
- Snackbar for notifying about failed imports

## v0.5.12

- admin page for failed imports
- snackbar tells admins when scans are happening
- report the latest version available in the browser footer tooltip
- admin flag for disabling codex for non-users

## v0.5.11

- browser rows now adapt to browse tile size
- browser covers for containers now match data we're sorting by
- reader fix settings for all comics were not setting properly
- fix bookmarks for sessions that aren't logged in
- serve static files faster

## v0.5.10

- fix filtering bugs
- fix mark read/unread bugs
- fix reader settings not setting properly
- fix reader images positioning
- fix minor crash closing books with unitialized browser app

## v0.5.9

- fix sorting for folder view
- display sort key value in browse tile
- display standard image for missing covers
- slightly more helpful 404 page
- comicbox 0.1.4 fixes several import bugs

## v0.5.8

- Upload mistake with 0.5.7. This is just a version bump.

## v0.5.7

- update comicbox to v1.3 should fix many import crashes
- allow credits with an empty role
- pagination of large browse results
- center comic pages better
- add download link to browser menu
- log to files as well as console
- remove scan locks on startup

## v0.5.6

- websocket path security was handling leading slashes badly. just skip it.

## v0.5.5

- Revert to whitenoise 5.1.0 which works with subpaths

## v0.5.4

- Fix crash on start if all static dirs do not exist.

## v0.5.3

- Fixed login bug introduces in v0.5.3 (thanks hubcaps)
- Fixed filtering bug introduced in v0.5.2
- Versioned API
- Toast popup for admins indicating libraries being scanned.
- Periodic frontend refresh during long scans.
- Codex version displayed in browser footer

## v0.5.2

- Lazy load filter choices when the menu opens
- Fix multiprocessing for Windows
- Documentation moved into admin panel

## v0.5.1

- Minor bugfixes. Rebuild for pypi

## v0.5.0

- Productionized alpha release

## v0.4.0

- Polished VueJS frontend

## v0.3.0

- Single Page VueJS frontend PoC without much styling

## v0.2.0

- Working application with all initial features
- Django frontend

## v0.1.0

- Proof of concept.
