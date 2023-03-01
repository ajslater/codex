# 📜 Codex News

<img src="codex/static_src/img/logo.svg" style="
height: 128px;
width: 128px;
border-radius: 128px;
" />

## v1.2.6

- Fix
  - Impose memory limits on search index writers.
  - Impose items before write limits search index writer.
  - Sort comics by path for the reader navigation when in Folder View.
  - Remove inappropriate vertical scroll bars from page images.

## v1.2.5

- Features:
  - In Folder View the reader navigates by folder instead of series.
- Fix:
  - OPDS crash on missing 24 hour time setting input required.

## v1.2.4

- Features:
  - User configurable 24 hour time format.
  - Reader
    - Displays covers as one page even in two page mode.
    - Read in Reverse mode.
    - Keymaps for adjusting page by one page in two page mode.
    - Previous and Next book navigation buttons and keymaps.
- Fix
  - OPDS:
    - Fix acquisition feed timeouts on large libraries by removing most m2m
      fields that populated OPDS categories
    - Fix pagination
    - Show series name in comic title.
    - Experiment: don't show top links or entry facets on pages > 1
  - Reader:
    - Two pages mode would skip pages.
    - Next/prev book goes to correct page for Right To Left tagged books.
    - Fix occasional error setting reader settings.
    - Fixed noop poll event happening on comic cover creation.

## v1.2.3

- Fix
  - Prevent search indexing starting over if it encounters errors.
  - Fix download buttons.
  - Fix admin settings drawer obscuring small screens.
  - Fix scroll bars showing inapproporately on admin tables.
  - Fix OPDS authors having 'i' appended.

## v1.2.2

- Fix
  - Fix all items removed from search index after update.
  - Speedups to cleaning up search engine ghosts.

## v1.2.1

- Fix
  - Crash on building a fresh database.
  - Fixed an importer crash when it tried to wait for changing files.
  - Disabling Library Poll prevented manual polling.
  - More explicit Poll Every hints in edit dialog.
  - Repository link didn't open a new window.

## v1.2.0

### What kind of Heaven uses bounty hunters?

- Features
  - Faster and more robust PDF support. Codex no longer depends on the poppler
    library.
  - LOGLEVEL=VERBOSE deprecated in favor of DEBUG
  - Stats page API accessible via API key as well as admin login.
- Fix
  - Some Librarian Status messages would appear never to finish.
- Development
  - The multiprocessing method is now S P A W N 💀 on all platforms.
  - Websockets are now handled by customized Django channels
    - aioprocessing Queue communicates between librarian and channels.

## v1.1.6

- Fix
  - Fix rare deletion and recreation of all comics when inodes changed.

## v1.1.5

- Features
  - Admin Stats tab
  - Libraries can have a poll delay longer than 1 day.
- Fix
  - Crash when removing comics.
  - Admin Create & Update dialogs would get stuck open on submit.
  - Delete expired and corrupt sessions every night.
  - More liberal touch detection for more devices.

## v1.1.4

- Fix

  - Multiprocessing speedup for large search engine indexing jobs
    - Writes search engine data in segments.
  - Search engine segment combiner optimizer runs nightly (and manually).

## v1.1.3

- Fix

  - Fix some OPDS browsers unable to read comics.

## v1.1.2

- Fix

  - Fix unable to initialize database on first run

## v1.1.0

### Whoosh

- Features
  - Switch to Whoosh Search Engine.
    - You may delete `config/xapian_index`.
  - May run on Windows now?
  - Moved db backups to `config/backups`.
  - Backup database before migrations.
- Removed
  - Do not store search history for combobox across sessions.
- Fix
  - Fix Admin Library folder picker.
  - Uatu does a better job of ignoring device changes.
  - Don't pop out of folder mode on searches.
  - Fix showing error on unable to load comic image.

## v1.0.3

- Features
  - Force update all failed imports admin task.
- Fixes
  - Fix moving folders to subfolder orphans folders bug.
  - Fix id does not exist redirect loop.

## v1.0.2

- Features
  - Support for Deflate64 zip compression algorithm.
- Fixes
  - Fix Failed Imports not retrying import when updated.
  - Make db updates more durable and possibly problem comics paths in log.
  - Discard orphan websocket connections from the connection pool.
  - Fix Admin Status drawer closing at wrong time.

## v1.0.1

- Features
  - Justify order-by field in browser cards.
- Fixes
  - Fixed next book change drawer opening settings drawer.
  - Fixed zero padding on browser card issue numbers.

## v1.0.0

### Vue 3

- Features
  - Removed old django admin pages.
  - Shutdown task for admins.
  - Configure logging with environment variables. See README.
- Fixes
  - Fix displaying error in login dialog.
  - Fix saving community & critical rating filters to session
  - Fix fit to screen not enlarging pages smaller than screen.
- Developer
  - Frontend is now Vuetify 3 over Vue 3. Using options API.

## v0.14.5

- Fixes

  - Fix crash on decoding some comics metadata charset encoding.

## v0.14.4

- Fixes

  - Fix login not available when AdminFlag Enable Non Users was unset.
  - Fix server PicklingError logging bug.

## v0.14.3

- Fixes

  - Fix root_path configuration

## v0.14.2

- Fixes

  - Fix Librarian process hanging due to logging deadlock.
  - Fix reader keyboard shortcut help.
  - Fix book change drawer appearing in the middle of books.

## v0.14.1

- Fixes

  - Resolve ties in browser ordering with default comic ordering.
  - Always close book change drawer before reader opens.

## v0.14.0

### Sliding Pages

- Features
  - Animated sliding pages on reader.
  - Comic & PDF pages display loading, rendering and password errors.
- Fixes
  - Filters with compound names were not loading choices.
  - Show only usable filters for current view as filter choices.
  - Allow filtering by None values when None values exist.
  - Handle an iOS bug with downloading pages and comics inside a PWA.
  - Fixed PDF failure to render on load and after changing settings.
  - Login & Change Password dialogs no longer activate Reader shortcuts by
    accident.

## v0.13.0

### Admin Panel

- Features
  - Single Page Admin Panel.
  - Users may now change their own passwords.
  - OPDS
    - Use facets for known User Agents that support them. Default to using entry
      links.
    - Gain a Newest Issues facet, a Start top link and a Featured / Oldest
      Unread link.
    - More metadata tags.
    - Special thanks to @beville for UX research and suggestions
  - HTTP Basic auth only used for OPDS.
  - Frontend components do lazy loading, should see some speedups.
- Fixes
  - Fixed imprints & volume levels not displaying sometimes.
  - Fix large images & downloads for some OPDS clients.
- Developer
  - API v3 is more restful.
  - /api/v3/ displays API documentation.
  - Vite replaces Vue CLI.
  - Pina replaces Vuex.
  - Vitest replaces Jest.
  - Django livereload server and debug toolbar removed.

## v0.12.2

- Fixes
  - Fix OPDS downloading & streaming for Chunky Comic Reader.
  - Hack in facets as nav links for Panels & Chunky OPDS readers.

## v0.12.1

- Fixes
  - Disable article ignore on name sort in folder view.
  - Fix browser navigation bug with issues top group.

## v0.12.0

### Syndication

- Features
  - OPDS v1, OPDS Streaming & OPDS Search support.
  - Codex now accepts HTTP Basic authentication.
    - If you run Codex behind a proxy that accepts HTTP Basic credentials that
      are different than those for Codex, be sure to disable authorization
      forwarding.
  - Larger browser covers.
  - Sort by name ignores leading articles in 11 languages.
- Fixes
  - Use defusexml to load xml metadata for safety.
  - Removed process naming. My implementation was prone to instability.

## v0.11.0

### Task Monitor

- Features
  - Librarian tasks in progress appear in the settings side drawer for
    adminstratiors.
  - Covers are now created on demand by the browser, rather than on import.
  - Browser Read filter.
- Fixes
  - Bookmark progress bar updates in browser after closing book.
  - Metadata web links fix.

## v0.10.10

- Features

  - Reader nav toolbar shows position in series.

- Fixes
  - Fix inability to log in when Enable Non Users admin flag is unset.
  - Simplify Admin Library delete confirmation page to prevent OOM crash.
  - Move controls away from iphone notch and home bar.

## v0.10.9

- Fixes

  - Fix null bookmark and count fields in metadata
  - Fix indeterminate finished state when children have bookmark progress.
  - Fix maintenance running inappropriately on first run. Crashed xapian
    database.
  - Fix reader metadata keymap

- Features

  - Progressive Web App support
  - Reader "Shrink to" settings replaced by "Fit to"

- Special Thanks
  - To ToxicFrog, who's been finding most of these bugs I'm fixing for a while.

## v0.10.8

- Fixes

  - Fixed reader nav clicks always showing the toolbars.
  - Attempt to fix unwanted browser toolbars when treated as mobile app
  - Wait half a second before displaying reader placeholder spinner.
  - Fix metadata missing search query.
  - Fix metadata cache busting.

- Features
  - Accessibility enhancements for screen readers.

## v0.10.7

- Features

  - Browser tries to scroll to closed book to keep your place.

- Fixes
  - Fixed missing lower click area on browser cards.
  - Fixed session bookmark interfering with logged in user bookmark.

## v0.10.6

- Broken docker container

## v0.10.5

- Features

  - Reader shrink to screen setting becomes fit to screen and embiggens small
    images.
  - Reader changing to the next book now has visual feedback and requires two
    clicks.

- Fixes
  - Removed vertical scrollbars when Reader shrunk to height.
  - Don't disturb the view when top group changes from higher to lower.

## v0.10.4

- Fixes

  - Fix double tap for non-iOS touch devices.

- Features
  - Shrink to Screen reader setting.
  - Reader throbber if a page takes longer than a quarter second to load.

## v0.10.3

- Fixes
  - Fix PDF going blank when settings change.
  - Remove vestigal browser scrollbars when they're not needed. Thanks to
    ToxicFrog.
  - Fix cover cleanup maintenance task.

## v0.10.2

- Fixes
  - URLS dictate view over top group. Fixes linking into views.
  - Fix possible cover generation memory leak.
  - Build a deadfall trap for search indexer zombies. Use Offspring's brains as
    bait.

## v0.10.1

- Fixes
  - Linked old top level comics orphaned by library folders migration.

## v0.10.0

### Portable Document Format

- Features

  - PDF support. Optional poppler-utils binary package needed to generate PDF
    cover thumbnails.
  - CBT support. Tarball comic archives.
  - Alphanumeric issue support. Requires rescanning existing comics.
  - Individual top level folders for each library.
  - Don't duplicate folder name in filename sort.

- Fixes
  - Comic file suffixes now matched case insensitively.
  - Finished comics count as 100% complete for bookmark aggregation.
  - Mark all folder descendant comics un/read recursively instead of immediate
    children.
  - Don't leak library root paths in Folder View for non-admins in the API.
  - Fixed aggregation bug showing inaccurate data when viewing group metadata.
  - More accurate Name sorting.
  - Fixed default start page for RTL comics.
  - Disabled reading links for empty comics.
  - Shield radiation from Venus to reduce zombie incidents.

## v0.9.14

- Fixes

  - Fix comicbox config crash.
  - Use codex config namespace (~/.config/codex) so codex doesn't interfere with
    standalone comicbox configs.
  - Comic issue numbers display to two decimal points instead of using ½ glyphs.

- Features
  - Filename order by option. Disabled if the "Enable Folder View" Admin Flag is
    off.

## v0.9.13

- Fixes
  - Fix root_path configuration for running codex in url sub-paths
  - Parse new filename patterns for metadata.
  - Slightly faster comic cover generation.

## v0.9.12

- Fixes

  - Fix setting global reader settings.
  - Fixed reader settings not applying due to caching.
  - Bust reader caches when library updates.
  - Reader titles smaller and wrap on mobile.
  - Fixed deep linking into reader.

- Features
  - Disable reader prev/next touch swiping for phone sized browsers.

## v0.9.11

- Fixed

  - Fixed covers not creating on import.
  - Covers update in browser when updated on disk.
  - Create missing covers on startup.
  - Bust browser cache when library updates.
  - Reader settings were not applying in some cases.
  - Fixed crash updating latest codex software version from the internet.
  - Fixed crash loading admin page.

- Features
  - Codex processes show names in ps and thread names on Linux.
  - Add Poll libraries action to FailedImports Admin Panel.
  - Space and shift-space previous and next reader shortcuts.
  - Reader settings UI redesigned to be clearer.

## v0.9.10

Yanked. Crash loading admin page.

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

### Private Libraries

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

### Search

- Features
  - Metadata search field in browser
  - Settings dialogs replaced with side drawers
  - Changed some keyboard shortcuts in reader.
  - "group by" renamed to "top group".
  - Admin panel gained a Queue Jobs page.
- Fixes
  - Browser does a better job of remembering your last browser view on first
    load.
  - Reader's "close book" button now does a better job returning you to your
    last browser view.
  - Metadata panel cleanup and fix some missing fields.
- Binary Dependencies
  - Codex now requires the Xapian library to run as a native application
- Drop Support
  - The linux/armhf platform is no longer published for Docker.
- License
  - Codex is GPLv3

## v0.7.5

- Fix integrity cleanup check for old comic_folder relations that prevented
  migrations.

## v0.7.4

- Fix integrity cleanup check for more types of integrity errors that may have
  prevented clean db migrations.
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

### Feels Snappier

- Database Migration

  - v0.7.0 changes the database schema. Databases run with v0.7.0+ will not run
    on previous versions of codex.

- Features

  - Big speed up to importing comics for large imports.
  - Speed up creating comic covers on large imports.
  - Admin Panel options for polling (formerly "scanning") and watching events
    have changed names.
  - Admin Panel task added to regenerate all comic covers.
  - Browser Admin Menu option added for polling all Libraries on demand.
  - Comics with no specified Publishers, Imprints and Series no longer have
    induced default names for these but have no name like Volumes.
  - Codex repairs database integrity on startup.
  - Codex backs up the database every night.
  - Autodetect server timezone (for logging).
  - Use TZ and TIMEZONE environment variables to explicitly set server timezone.
  - Added `VERBOSE` logging level to help screen out bulk `DEBUG` messages from
    dependencies.
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

### Better Filtering and Sorting

- New Filters
- New sort options: Updated Time and Maturity Rating
- New frontend URL scheme
- New API
- Added time to the browse card when sorting by time fields
- Fixed a bug importing Story Arc Series Groups and Genres. Requires re-import
  to correct.
- Fixed a bug with sorting that grouped improperly and showed the wrong covers
  for reverse sorts.
- Browser pagination footer now remains fixed on the page
- Browser pagination footer is now a slider to handle larger collections
- Notifications now appear in reader as well as browser
- Scanning notifications on login not disappearing bug squashed
- On comic import failure, log the path as well as the reason
- Fixed a bug where the browser settings menu wouldn't close when opening a
  dialog
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

### First useful working version

- Productionized alpha release

## v0.4.0

### Polished UI

- Polished VueJS frontend

## v0.3.0

### I'm a frontend developer

- Single Page VueJS frontend PoC without much styling

## v0.2.0

### It's alive

- Working application with all initial features
- Django frontend

## v0.1.0

### Hello world

- Proof of concept.
