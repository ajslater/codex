# 📰 Codex News

## v0.9.10

- Fixed

  - Fixed covers not creating on import.
  - Covers update in browser when updated on disk.
  - Create missing covers on startup.
  - Bust browser cache when library updates.
  - Reader settings were not applying in some cases.

- Features

  - Codex processes show names in ps and thread names on Linux.
  - Add Poll libraries action to FailedImports Admin Panel.
  - Space and shift-space previous and next reader shortcuts.
  - Reader settings UI redisigned to be clearer.

## v0.9.9

- Fixed

  - Fixed combining CBI credits with other format credits
  - Failed imports notification appears only for new failed imports.

- Features

  - Update search index daily.
  - Clean up orphan comic covers every night.

## v0.9.8

- Fixed

  - Fixed search index update crash while database is still updating.
  - Fixed issues larger than 99 bug.
  - Fixed issue not imported due to metadata cleaning bug.
  - Fixed crash updating search index while library was still updating.
  - Thread error trapping and diagnostics to root out zombie process issue.
  - Sort numeric terms in filter menus numerically not alphabetically.
  - Fixed comic name display wrapping in browser.

- Features

  - More comprehensive metadata sanitizing before import.
  - Reduced time checking to see if files have finished writing before import.
  - Uniform format for metadata parsing logging.
  - Credits sorted by last name.

## v0.9.7

- Fixed

  - Coerce decimal values into valid ranges and precision before importing.

- Features

  - Clean up unused foreign keys once a day instead of after every import.
  - Clean up unused foreign keys librarian job available in admin panel.

## v0.9.6

- Fixed

  - Don't open browser when a library changes when reading a comic.
  - Fixed crash creating illegal dates on import.

- Features

  - Replace description field with more common ComicInfo comments field.
  - Log files now rotate by size instead of daily.
  - Log path for failed imports and cover creation.

## v0.9.5

- Fixed

  - Use an allow list for importing metadata to prevent crashes.

## v0.9.4

- Fixed

  - Fixed crash when importing comments metadata.

## v0.9.3

- Fixed

  - Import credits data for CBI and CIX tagged comics.
  - More liberal metadata decimal parsing.

## v0.9.2

- Fixed

  - Fix rare migration bug for Cover Artist role.

## v0.9.1

- Fixes

  - Fix to library group integrity checker

## v0.9.0

_Private Libraries_

- Features

  - Libraries may have access restricted to certain user groups.
  - The "Critical Rating" tag is now a decimal value.
  - The "Community Rating" tag replaced "User Rating" tag, a decimal value.
  - Cover Credits role replaced by "Cover Artist".
  - Reader has a "Download Page" button.
  - Metadata dialog highlights filtered items.
  - Metadata dialog is faster.
  - Admin Queue Job for creating missing comic covers.

## v0.8.0

_Search_

- Features

  - Metadata search field in browser
  - Settings dialogs replaced with side drawers
  - Changed some keyboard shortcuts in reader.
  - "group by" renamed to "top group".
  - Admin panel gained a Queue Jobs page.

- Fixes

  - Browser does a better job of remembering your last browser view on first load.
  - Reader's "close book" button now does a better job returning you to your last browser view.
  - Metadata panel cleanup and fix some missing fields.

- Binary Dependencies

  - Codex now requires the Xapian library to run as a native application

- Drop Support

  - The linux/armhf platform is no longer published for Docker.

- License

  - Codex is GPLv3

## v0.7.5

- Fix integrity cleanup check for old comic_folder relations that prevented migrations.

## v0.7.4

- Fix integrity cleanup check for more types of integrity errors that may have prevented clean db migrations.
- Fix last filter, group, sort not loading properly for some new views.

## v0.7.3

- Fix crash updating latest version.
- Fix a folder not found crash in folder view.
- Database indexing speedups.

## v0.7.2

- Fix another integrity check bug

## v0.7.1

- Fix and integrity check crash that happened with an older databases.
- Added `CODEX_SKIP_INTEGRITY_CHECK` env var.

## v0.7.0

_Feels Snappier_

- Database Migration

  - v0.7.0 changes the database schema. Databases run with v0.7.0+ will not run on previous versions of codex.

- Features

  - Big speed up to importing comics for large imports.
  - Speed up creating comic covers on large imports.
  - Admin Panel options for polling (formerly "scanning") and watching events have changed names.
  - Admin Panel task added to regenerate all comic covers.
  - Browser Admin Menu option added for polling all Libraries on demand.
  - Comics with no specified Publishers, Imprints and Series no longer have induced default names for these but have no name like Volumes.
  - Codex repairs database integrity on startup.
  - Codex backs up the database every night.
  - Autodetect server timezone (for logging).
  - Use TZ and TIMEZONE environment variables to explicitly set server timezone.
  - Added `VERBOSE` logging level to help screen out bulk `DEBUG` messages from dependencies.
  - Truncated logging messages for easier reading.

- Fixes
  - Fixed metadata screen displaying incorrect information.
  - Now compatible with python 3.10.

## v0.6.8

- Fixes
  - Fixes some import bugs with filename parsing when there are no tags
  - Fixed two page view toggle hotkey
- Features
  - Browser now tells you what kind of items you're looking at.
  - Reader swiping navigation
  - Reader keyboard shortcut help dialog
  - Tentative linux/armhf support. No way for me to test this
  - Vacuum the sqllite database once a day to prevent bloat
  - Corrupt database rebuild procedure. See README.

## v0.6.7

- Dark admin pages and fix template overrides.

## v0.6.6

- Automate multi-arch builds

## v0.6.5

- Build Docker images for amd64 & arm64 manually.

## v0.6.4

- Fix reader bug that only displayed first page

## v0.6.3

- Add LOGLEVEL environment variable.
  - Set to DEBUG to see everything.
- Removed DEV environment variable.
- Possible fix for newly imported covers not displaying.

## v0.6.2

- Fixed intermittent Librarian startup crash in docker.
- Fixed DEBUG environment variable to be able to run in production.
- Added DEV environment variable for dev environment.

## v0.6.1

- Fix librarian startup crash. Prevented admin actions from happening.

## v0.6.0

_Better Filtering and Sorting_

- New Filters
- New sort options: Updated Time and Maturity Rating
- New frontend URL scheme
- New API
- Added time to the browse card when sorting by time fields
- Fixed a bug importing Story Arc Series Groups and Genres. Requires re-import to correct.
- Fixed a bug with sorting that grouped improperly and showed the wrong covers for reverse sorts.
- Browser pagination footer now remains fixed on the page
- Browser pagination footer is now a slider to handle larger collections
- Notifications now appear in reader as well as browser
- Scanning notifications on login not disappearing bug squashed
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

- Metadata popup is now faster.
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
- fix minor crash closing books with uninitialized browser app

## v0.5.9

- fix sorting for folder view
- display sort key value in browse tile
- display standard image for missing covers
- slightly more helpful 404 page
- fix import bugs

## v0.5.8

- Upload mistake with 0.5.7. This is just a version bump.

## v0.5.7

- fix import crashes
- allow credits with an empty role
- pagination of large browse results
- center comic pages better
- add download link to browser menu
- log to files as well as console
- remove scan locks on startup

## v0.5.6

- websocket path security wasn't handling leading slashes well. Skip it.

## v0.5.5

- Revert to whitenoise 5.1.0 which works with subpaths

## v0.5.4

- Fix crash on start if all static dirs do not exist.

## v0.5.3

- Fixed login bug introduces in v0.5.3 (thanks hubcaps)
- Fixed filtering bug introduced in v0.5.2
- Versioned API
- Toast popup for admins indicating libraries are scanning.
- Periodic frontend refresh during long scans.
- Codex version displayed in browser footer

## v0.5.2

- Lazy load filter choices when the menu opens
- Fix multiprocessing for Windows
- Documentation moved into admin panel

## v0.5.1

- Minor bugfixes. Rebuild for pypi

## v0.5.0

_First useful working version_

- Productionized alpha release

## v0.4.0

_Polished UI_

- Polished VueJS frontend

## v0.3.0

_I'm a frontend developer_

- Single Page VueJS frontend PoC without much styling

## v0.2.0

_It's alive_

- Working application with all initial features
- Django frontend

## v0.1.0

_Hello world_

- Proof of concept.
