# 📜 Codex News

<img src="codex/img/logo.svg" style="
height: 128px;
width: 128px;
border-radius: 128px;
" />

## v1.9.14

- Fixes:
    - Fix bad href validation in OPDS v2 leading to null links and therefore
      invalid OPDS.

## v1.9.13

- Change:
    - Codex only accepts auth tokens prefixed with the Bearer header.
- Fixes:
    - Fix crash on API schema generation.
    - Fix scribe daemon not shutting down properly.
    - Fix Swagger API docs crash.
    - Fix full text search barfing on single quoted terms.
    - Return 401 and authorization v1 json to OPDS instead of 403 on auth
      failure more often.
- Features:
    - OPDS order by filename.

## v1.9.12

- Fixes:
    - Fix accepting OPDS v2 progression correct Content-Type.
    - Fix parsing OPDS v2 progression position.
    - Fix bookmark update crash.

## v1.9.11

- Fixes:
    - Fix OPDS v1 pagination.

## v1.9.10

- Fixes
    - Fix Remote-User authorization for proxy setting http headers.
    - Fix order links not appearing in OPDS v1
- Feature:
    - Allow "Bearer" header for token authentication in addition to "Token"

## v1.9.9

- Fixes
    - Access control bug would let users see comics in include groups they were
      not a part of.
    - Remove redundant top links from OPDS v2 facets group block.
    - Fixed a status crash.
- Features
    - Remote-User HTTP header SSO support activated by an environment variable.
      See docs.
    - HTTP Header Auth Tokens are now accepted as authorization. Useful for OPDS
      and possibly some SSO setups.

## v1.9.8

- Bad release. Does not start.

## v1.9.7

- Fixes
    - Fix OPDS v2 manifest/reading crash.
    - Fix OPDS v2 search.

## v1.9.6

- Fixes
    - Fix OPDS feed crash.

## v1.9.5

- Fixes
    - Fix settings not resetting to default on OPDS start pages.
    - Isolate OPDS settings from web settings so they don't reset each other.

## v1.9.4

- Fixes
    - Fix unnecessary redirects in OPDS v1 & v2 search.

## v1.9.3

- Fixes
    - Unnecessary redirect going to OPDS v1 start page.
    - Fixed start page link in OPDS v2.0

## v1.9.2

- Fixes
    - OPDS 2.0 homepage preview sections were showing the wrong queries.
    - OPDS 2.0 progression bookmarking was broken. Stump doesn't seem to be
      transmitting progression data yet, though.
- Features
    - OPDS 1.0 gains a homepage similar to OPDS v2
    - OPDS start page URLS are now different. See the OPDS popup dialog.

## v1.9.1

- Fixes
    - OPDS v2 fix crash on faceted views.

## v1.9.0 - OPDS 2.0 Redesign

- Fixes
    - Fix crash in OPDS v2 feed.
- Features
    - Redesigned OPDS v2 to work with Stump & Readest Clients
    - Docker healthcheck endpoint. See docs.

## v1.8.22

- Fixes
    - Fix reading books crash that crept into the last release.

## v1.8.21

- Fixes
    - Fix Close Book button linking to parent of desired route.

## v1.8.20

- Fixes
    - Fix dragging when zoomed in in reader when using mouse left button.
    - Fix weird spacing and borders on browser and reader toolbars.
    - Attempt to make Close Book route in reader more accurate.

## v1.8.19

- Fixes
    - Do not sanitize Library and Comic path names. Fixes an import crash on
      paths with dangerous looking strings in them.
    - Fix a crash when moving comics.

## v1.8.18

- Fixes
    - Filter and Search parameters were being applied after clearing.
- Features
    - Read metadata from PDF embedded files.

## v1.8.17

- Features
    - Python 3.14 support.

- Fixes
    - Fix for codex sometimes shutting when asked to restart.

## v1.8.16

- Don't support Python 3.14 until dependencies do.
- Docker image is now based on trixie debian

## v1.8.15

- Performance
    - Replace axios with xior AJAX library.

## v1.8.14

- Fixes
    - Fix settings not saving in reader and sometimes in browser.
    - Fix shutdown and restart signals on Windows.

## v1.8.13

- Fixes
    - Fix import crash when metadata import is disabled.

## v1.8.12

- Fixes
    - Fix publishers and series tags disappearing. Use Library Force Update to
      restore them.
    - Fix credit role order in tags screen.

## v1.8.11

- Fixes
    - Restarting Codex with Codex would still crash. More comprehensive fix.

## v1.8.10

- Fixes
    - Restarting Codex with Codex would crash, so Auto-Update restarts were
      broke.
        - Sorry non-docker homies! Thanks @professionaltart.
    - Fix universes not being search indexed (very rare).
    - More reliable re-render for browser page slider and navigation buttons.

## v1.8.9

- Fixes
    - Attempt to fix not saving new stat values if update doesn't update comic
      metadata.
    - Attempt to fix import bug where update metadata is disposed of before it
      can be applied.
    - Attempt to fix browser page slider not updating to match the current
      folder.

## v1.8.8

- Fixes
    - Fix import crash on some Metron tagged comics with a primary identifier
      source.

## v1.8.7

- Fixes
    - Make Full Text Search table smaller. Some irrelevant fields and data were
      causing exponential bloat, crippling large libraries.
    - Fix search by field for string fields, identifiers and issue.
    - Fix overflow on browser card titles.

## v1.8.6

- Fixes
    - Scale search index sync batch size with memory. Large search sync query
      was preventing search sync of large databases on small machines.

## v1.8.5

- Fixes
    - Better fix for persistent settings. Old fix could lead to settings that
      never clear.

## v1.8.4

- Fixes
    - Fix not importing page_count when import metadata is off, leads to
      unreadable books.
    - Fix persistent settings.

## v1.8.3

- Fixes
    - Fix searching by string like fields in the search bar like 'path'.
    - Fix minor search update exception when there's nothing search related to
      update on import.

## v1.8.2

- Fixes
    - Force docker logs (all stdout logs) to colorize output.

## v1.8.1

- Fixes
    - Fix minor search update exception.

## v1.8.0

- Features
    - Support
      [MetronInfo.xml v1.0 Schema](https://metron-project.github.io/docs/category/metroninfo)
      for comic metadata.
    - Support CB7 (7zip) comic archives.
    - Search Indexing now also done in the import phase which is faster than
      syncing from the db:
        - 20k comics both imported and indexed in 9 minutes on my old macbook at
          a rate of 30 comics per second. Half a million comics might take less
          than 5 hours on the same machine.
        - However this update replaces the search index and Codex will sync the
          search index when it starts.
    - Fewer database updates when comics change metadata or don't change
      metadata at all means fewer and faster update imports.
    - New Tags:
        - Add Universes. Main Characters, and Main Team marked with a ★.
        - Metron tags can provide links to web databases for each tag.
    - New Import Metadata on Demand Admin Flag.
    - Add manual Import Abort task for admins.
    - Browser tab titles show route and page title, no longer show custom
      banner.
    - Logging format changed.

- Fixes
    - Reading Order in reader was not always defaulting to your last Browser Top
      Group.
    - Fixed filtering on Critical Rating and FileType
    - Fixed searching on Critical Rating field.
    - Bug displaying Age Rating, Original Format, Scan Info, Tagger in metadata.
    - Fixed database locking crashes.
    - Attempt to fix major version change CSRF errors by forcing logout if CSRF
      errors occur.

- Dev
    - Uses Comicbox 2.0 see
      [Comicbox NEWS for all details](https://github.com/ajslater/comicbox/blob/main/NEWS.md)

## v1.7.15

- Fixes
    - Fix unable to change top group to folders or story arcs if on root browse
      page.

## v1.7.14

- Fixes
    - Fix Reader jumping back into the same book when changing to a new book.

## v1.7.13

- Fixes
    - Fix Reader Reading Order dropdown unable to change reading order.
    - Fix loading root browser pages greater than 1 as a new route.
    - Missing books error screen had no toolbars, could not close it.
    - Fix docker configuration for Synology by creating a comicbox config
      directory.
    - Wait to load browser and reader pages until login tried with a cookie.

- Features
    - Experimental `CODEX_BROWSER_MAX_OBJ_PER_PAGE` env variable. Default
      is 100.

## v1.7.12

- Fixes
    - Crash downloading comics when user is in a group.
    - User last active activity was often not recorded.

- Features
    - Animate Pages option toggle in reader settings

## v1.7.11

- Fixes
    - Fix importing of story arc tags

## v1.7.10

- Fixes
    - Fix occasional import link tags crash.

## v1.7.9

- Fixes
    - Tags page layout fixes.

## v1.7.8

- Features
    - Tags page layout changes with more notes from @beville.

- Fixes
    - Tags for simple comic fields were incorrectly taken from the first comic
      in a group.
    - Filter menu wasn't populating for top folder.
    - Librarian status tasks would appear out of order.

## v1.7.7

- Fixes
    - Fix Librarians Statuses not loading in UI.
    - Tags screen crash with untagged series or volumes.
    - Fix tags screen Mark Read confirmation names.
    - Order Tags Contributors by relevance not alphabetically.

## v1.7.6

- Features
    - Always Show Filenames setting for browser cards.
    - Tags page layout changes with notes from @beville.

- Fixes
    - Fix import crash on files with escapable html characters or utf-8 chars in
      the filename.
    - Fix page range crash in reader.
    - Fix overzealous escaping of html in metadata strings.
    - Fix group tags not aggregated properly in metadata screen for folders and
      story arcs.

## v1.7.5

- Fixes
    - More granular websocket notifications means the web UI does fewer more
      targeted data updates.
    - Prevent deactivating and deprivileging the logged in user.
    - Fix resetting active flag when resetting admin user with environment
      variable.
    - Fix crash in auto-update when unable to determine current Codex version.

## v1.7.4

- Fixes
    - Fix setting bookmarks and book settings bug.
    - Sanitize HTML out of imported comic metadata fields and admin inputs.

## v1.7.3

- Features
    - Browser Order By Child Count.
    - Customized site title option in Admin Flags.
    - Codex logs are now compressed when rotated.
    - Support OPDS v2.0 Progression (streaming) draft proposal from Aldiko.

- Fixes
    - Browser Group Mark Read/Unread obeys browser filters.
    - Fixed bad redirect when to deep linking into browser Folders or Story
      Arcs.
    - Fixed order by name for issues disregarding volume names in browser and
      reader
    - Fix display of name and filename on browser cards.
    - Fix batching import of Contributors to prevent crash on large imports.
    - Fixed an OPDS Metadata crash.

## v1.7.2

- Features
    - Download entire groups of comics from the browser and metadata screens.

- Fixes
    - Fix reader page API sometimes crashing.

## v1.7.1

- Features
    - Always display filename for comics on browser cards in Folder View
    - Detect .jxl extension (JPEG XL) as a comic page.

- Fixes
    - Fix ignoring MacOS resource forks in archives.
    - Don't redirect to issue view on first search in Folder View

## v1.7.0

- Features
    - Search
    - Use SQLite Full Text Search v5 for search engine.
    - Search syntax has changed. See the help popup at the end of the search
      bar.
    - Use faster db column lookups for some search bar queries. Thanks
      @bmfrosty.
    - You may remove the directory `config/whoosh_index`.
    - Integrity Checks
    - Faster more comprehensive db integrity checks run every night instead of
      at startup.
    - Integrity checks can run on startup with environment variables documented
      in README.

- Fixes
    - Actually fix browser opening reader at correct bookmark.
    - Also fixes progress calculation on browser cards.
    - Fixed crashes when the upstream codex version is not accessible.
    - Fixed possible race conditions with nightly maintenance.

## v1.6.19

- Fixes
    - Fix browser opening reader at correct bookmark.
    - Fix for browser triple tap bug for android tablet browsers in desktop
      mode.
    - Fix populating arcs in reading order menu in reader.
    - Fix submitting old arc to reader API.
    - Fix Version API blocking. Add check version admin task.
    - Fix Library "Poll Every" validation.
    - Fix Metadata dialog not scrolling sometimes.
    - Fix file extension for downloaded PDF pages.

## v1.6.18

- Yanked. Broken Reader.

## v1.6.17

- Features
    - Admin Action buttons now responsive to view size.

- Fixes
    - Auto update wasn't comparing versions well.
    - Possible fix for initializing admin flags crash.

## v1.6.16

- Fixes
    - Import may have been marking mounted drive's comics modified
      inappropriately.
    - Import crash when moving comics.
    - Relink deep orphan folders in the db instead of recreating them.
    - Do not adopt orphan folders deleted from the filesystem.
    - Admin Tab change password for user broke.
    - More robust ui cache busting on library update.
    - Fix minor error on metadata text boxes with null values.

## v1.6.15

- Fixes
    - Fix more Metadata links to browser groups not computing and resolving
      properly.

## v1.6.14

- Fixes
    - Fix Metadata links to browser groups not resetting topGroup properly.

## v1.6.13

- Fixes
    - Admin Panel Link was showing in the admin panel, not in the browser or
      reader.

## v1.6.12

- Features
    - Native Windows installation instructions in the README thanks to
      @professionaltart.
    - Anonymously send stats to improve Codex. See admin/flags for description
      and opt-out.

- Fixes
    - Detect iOS devices in Desktop Mode for proper iOS tap behavior.

## v1.6.9, v1.6.10, v1.6.11

- Yanked. Bad network behavior. Broken javascript.

## v1.6.8

- Fixes
    - Fix OPDS streaming in lazy metadata mode for Chunky-like readers which
      require a page count.

## v1.6.7

- Fixes
    - OPDS authorization for some readers
    - Remove superfluous debug exception trace on timezone endpoint.

## v1.6.6

- Fixes
    - User creation in admin panel broke.
    - There was confusing UI on admin panel unauthorized screen.

## v1.6.5

- Fixes:
    - Fix logout button not working.

## v1.6.4

- Fixes:
    - Reader crash loading reader order arcs.
    - OPDS datetimes now uniformly served in iso format.
    - Fix browser filter menus clearing and loading irregularities.
    - Fix parsing negative issue numbers in filenames.
    - Log common non-ComicBookInfo archive comments with less alarm.
- Removed
    - LOGLEVEL=VERBOSE deprecated for a long time. Use LOGLEVEL=DEBUG

## v1.6.3

- Features
    - Reader inherits the last browser view, with filters, as it's default
      reading arc.
    - When browser page is less than 1, redirect to parent. When 1 and empty,
      show empty page.
- Fix
    - The cover api was not accepting http basic (opds) authentication.

## v1.6.2

- Fixes
    - Fix pagination with more than 100 comics in the browser.

## v1.6.1

- Features
    - Add a retry button on book load error and page load error pages.

- Fixes
    - Fix unable to login if anonymous users prohibited.
    - Fix filter crash.
    - Metadata was showing incorrect groups for individual comics

## v1.6.0

- Features
    - Custom Covers for Folders, Publishers, Imprints, Series and Story Arcs.
    - Browser setting to choose Dynamic or First group covers. Thanks @Thakk.
    - Breadcrumbs in the browser
    - Reader can read by Volumes as well as by Series, Folder and StoryArc.
    - More compact UI controls.
    - Metadata tags can click to browse filtered on that tag.
    - Experimental API throttling support. Search the README for "throttle".
    - Add websocket updates for anonymous sessions
    - Speed and caching optimizations.
- Fixes
    - OPDS http basic authorization fixed.
    - Groups with the same name in different cases collapse into one group in
      the browser.
    - Order By respects browser show groups settings.
    - Fixed re-import of urls and identifiers.
    - Fixed cleanup of some foreign keys when no longer used.
    - Clean up all orphan folders on startup instead of first pass
    - Fix creating bookmarks.
    - Update browser sessions for user when users finish a book.

## v1.5.19

- Fixes
    - Metadata crash on folders.

## v1.5.18

- Fixes
    - Ignore comic pages from dotfiles and macOS resource forks.

## v1.5.17

- Fixes
    - Fix background color of browser card controls since vuetify update.

## v1.5.16

- Fixes
    - Fix creating and updating exclude groups.
    - More Web & url tags parsed from metadata.

## v1.5.15

- Fixes
    - OPDS streaming broken for some clients (Chunky) without metadata.
    - OPDS redirects for empty pages or 404's were crashing.
    - OPDS uses filename fallback for title if missing metadata.

## v1.5.14

- Features
    - Relative folder path is now searchable if Folder View enabled.
    - More granular caching hopefully for better performance.
- Fixes
    - OPDS redirects were crashing.
    - Null search was crashing metadata for single comics
    - Fix a breakage with fast file static file serving.
    - Change browser order by to something sensible when search cleared.

## v1.5.13

- Fixes
    - Fix root folder for library sometimes not created on import.
    - Fix redirect loop in browser when all members of a group deleted.
    - Fix browser pagination buttons not advancing.
    - Fix OPDS v2 crash
    - Fix browser throbber not appearing when making query.

## v1.5.12

- Fixes
    - Fix Folder browser offset pagination bug for folder with books and no
      folders.

## v1.5.11

- Fixes
    - Fix erroneous Folder View page out of bounds redirect.

## v1.5.10

- Fixes
    - Folder view was not showing all the books on mixed folder & book pages.
    - Shutdown and Restart admin tasks were not working.

## v1.5.9

- Fixes
    - Crash when reading comics in folder view introduced in v1.5.8

## v1.5.8

- Fixes
    - No search results was returning every comic instead of no comics.
    - issue: field searching returned no results.
    - issue_number, community_rating, & critical rating no longer require two
      digits of precision.
    - Excess books included in reader arc/folder/series.
- Features
    - Even Lazier import when Import Metadata Admin flag turned off.
    - issue: field search now combines numeric and suffix parts.

## v1.5.7

- Fixes
    - Pagination crash with more than 100 folders.
    - Experimental fix for Synology Docker CHOWN_PYTHON_SITE_PACKAGES=1

## v1.5.6

- Fixes
    - Fix sqlite limit crash when importing > \~1000 web urls.

## v1.5.5

- Fixes
    - Attempt to fix import crash processing too much metadata at once. Allow
      undocumented env variable to manipulate this: CODEX_FILTER_BATCH_SIZE
      (default: 900)
    - Fix search engine update crash for large collections.

## v1.5.4

- Fixes
    - Django 5 broke root_path prefixing from the asgi server. Work around it.

## v1.5.3

- Fixes
    - Mouse horizontal scroll broken on Firefox.

## v1.5.2

- Fixes
    - OPDS titles were showing as "Unknown" for comics with tagged volumes.
    - OPDS v2 was crashing.
    - Cover displayed for group browser with Name ordering was inconsistent.
    - Enable mouse drag horizontal scrolling in reader zoom mode.

## v1.5.1

- Fixes
    - OPDS v1 was not rendering any data.

## v1.5.0

- **Warning**
    - The main database path has changed from `db.sqlite3` to `codex.sqlite3`
    - This version forces a rebuild of the search index (not the main database)
- Fixes
    - Some integrity checks weren't running on startup.
    - The metadata page would sometimes crash for Admins.
    - Moving a comic to a subfolder would crash.
    - Moving a deep subfolders would crash.
    - Moving a comic to the root folder would send the comic to the phantom
      zone.
    - Updating comics would sometimes not delete removed tags.
    - Series & Volumes no longer updated too often on import.
    - Admin Actions was polling all libraries when one selected.
    - OPDS was showing repeated titles.
    - Vertical scroller tracking and updating improved.
    - Page filenames are now sorted case insensitively which should improve
      order.
- Features
    - Admin Exclude groups compliment the existing Include groups.
    - New metadata tags: Monochrome, Tagger, GTIN, Review, Identifiers, &
      Reading Direction. Available when comics are re-imported (Force Update
      recommended).
    - Identifiers metadata tag replaces the "Web" tag.
    - Reads ComicInfo.xml and other formats from the PDF keywords field. You can
      write ComicInfo.xml to PDFs with comictagger.
    - Reading Direction reader setting replaces Reader's vertical & horizontal
      views.
    - Supports the MetronInfo metadata format (rare).
    - Filesystem events filtered to only the ones Codex handles.
    - Double-click to zoom on pages in reader.
    - Read PDF with browser in a new tab link.
    - Experimental checkbox for caching entire comic or PDF in the browser.
    - Admin Flag for disabling most metadata import.
- Dev
    - Using comicbox v1 for metadata import.

## v1.4.3

- Fixes
    - Crash on undecodable characters in metadata.
    - Search terms weren't applying to filter choices population.
    - Fix name ordering. Show series & volume in browser cards if it affects
      name ordering.
    - Shrink reader page change boxes to let toolbar activate on corner clicks.
- Dev
    - Big lint update.

## v1.4.2

- Fixes
    - Groups were not aggregating children properly when searched.
    - Search could break Folder View.
    - Changing the browser 'Order By' would sometimes not apply.
    - Attempt to fix stale books appearing on reader load.

## v1.4.1

- Fixes
    - A bug that prevented folder view from displaying under some circumstances.

## v1.4.0

- Features
    - Story Arc Top Group in Web & OPDS Browsers
    - Support multiple Story Arcs per comic.
    - Supports Mylar CSV StoryArc / StoryArcNumber extension to ComicInfo.xml
    - Show only filter options that affect the current browse level.
    - Reader has a Series/Folder/Story Arc order selector.
    - Reader shows filename instead of metadata title if you've been browsing in
      File View
    - Downloads now use the original filename from disk.
- Fix
    - Folder was view displayed but crashed in OPDS even if disabled by admin.

## v1.3.14

- Features
    - Better metadata extraction for PDFs.
    - Support for ComicInfo StoryArcNumber, Review and GTIN tags.
    - Order by Story Arc Number
    - Do not detect .cbr files if unrar is not on the path.
    - Display filename for comics in browser file view.
- Fixes
    - Import of ComicInfo Tags metadata.
    - Never removed old missing metadata when updated.
    - Error on moving folders.
    - Fix saving last route between sessions.
    - Better error messages if unrar is not on the path.
- Removed
    - Remove support for unrar.cffi

## v1.3.13

- Fixes
    - Group cover sometimes showing wrong cover for order.
    - Rare import crash.

## v1.3.12

- Features
    - OPDS 2 Last Read link.
- Fixes
    - Books without bookmarks could break parts of the reader.
    - Remove clipboard UI hints when clipboard isn't available.

## v1.3.11

- Features
    - Last Read Order By option for web and OPDS.
    - Some Order By options now have a default descending order.
    - OPDS 1 special top links limited to 100 entries.
- Fix
    - OPDS 1 links did not include filters or order information.
    - OPDS 1 page streaming broke.

## v1.3.10

- Fixes
    - Crash when reading from folder view.

## v1.3.9

- Features
    - Experimental OPDS 2.0 Support.
    - Create all comic covers admin task.
    - Faster Metadata pages for web and OPDS.
- Fixes
    - Two pages mode broken.
    - Credits not imported bug.
    - Failed imports not removed when file removed bug.

## v1.3.8

- Fixes
    - Fix Basic Authentication not enabled for OPDS Cover, Page, and Download
      views.
    - Tune low memory algorithm slightly lower for memory constrained systems.
- Dev
    - Use makefile and moved most scripts into bin.

## v1.3.7

- Feature
    - Metadata page links to groups to browse to.
- Fixes
    - Crash when moving comics.
    - Container memory limits weren't detected for Linux kernels before 4.5
    - Reader
    - Horizontal Reader was slow for comics with high page counts.
    - Vertical scroller was not tracking pages in fitTo Width or Orig modes.
    - Validation error detecting child and parent library paths incorrectly.
    - Dev
    - Django 4.2

## v1.3.6

- Fixes
    - Much lower memory tuning. Environment variables control tuning.
    - Possible fix for vertical scroller page tracking for tall images.

## v1.3.5

- Fixes
    - OPDS sorting and filtering broke.
    - Fixed Download URLs for clients that ignore headers like Chunky.
    - Update Search Index now checks for more missing entries.

## v1.3.4

- Fixes
    - Number out of range errors for issue when search indexing.
    - Total child pages of folders and groups sometimes overcounted, displaying
      half unread folders.
    - Reader: Vertical Scroll
    - Remove black bottom margin from images.
    - Was loading every page in a comic at once.
    - Page tracking did not work with images larger than viewport width.

## v1.3.3

- Fixes
    - Number out of range errors when search indexing.
    - Possible Search Index Remove Stale and Abort jobs not scheduled properly.
    - OPDS missing entry ids rejected by Panels reader.
    - Downloads had an extra period in the suffix.

## v1.3.2

- Fixes
    - Reader Fit To settings broken
    - Possible files marked modified too often.

## v1.3.1

- Fixes
    - An import crash in create foreign keys.
    - Admin table dates were always in UTC so sometime off by a day.

## v1.3.0

### I remember... my whole life. Everything

- Features
    - Codex stable in 1GB RAM environments. Faster with more.
    - Codex uses unrar-cffi if available. Not required.
    - Browser
    - Navigate to top button.
    - Filter by File Type.
    - OPDS
    - Top links display only at catalog root.
    - Extended metadata moved to alternate links.
    - Admin
    - Search Indexer Remove Stale Records task much faster.
    - Comic import speedups.
    - Fancier sortable admin tables.
    - Removed `max_db_ops` config variable.
- Fixes
    - Reader vertical scroll lost its place in Fit To Width or Orig mode.
    - OPDS downloaded files all had the same name.
    - Search Index
    - More robust against bad data.
    - Some search fields were case sensitive.
    - Admin
    - Graceful shutdown when Docker container stops.
    - Codex was backing up on every startup.
    - Status for batched imports (large imports or low memory) now reflects
      total instead of single batch.

## v1.2.9

- Features
    - Vertical scroll option for reader.
    - Faster search index removes.
    - Admin Users tab shows last user activity date.
    - OPDSE PSE 1.2 extension for Panels `pse:lastReadDate`
- Fixes
    - Fixed next and previous book keyboard shortcuts.
    - Improved OPDS acquisition page performance by removing more "categories"
      metadata.

## v1.2.8

- Features
    - Search Index
    - Improved search indexing times.
    - Admin Flag to adjust nightly full optimization.
    - OPDS
    - "Newest Issues" Link replaced by "Recently Added" after user feedback.
- Fixes
    - Volume tags were often not scanned. Recommend using Force Reimport on all
      libraries.
    - OPDS
    - Fix navigation links not inheriting view settings of current page.
    - Removed populating categories in OPDS to experiment with performance
      issues.
    - Fix OPDS pse lastRead tag.
    - Block library polling during database updates, fixes reindexing.

## v1.2.7

- Fixes
    - Trap final search index commit errors and try again without merging
      segments.
    - Fix moving folders assigned no parent folder, displaying them in root.

## v1.2.6

- Fixes
    - Impose memory limits on search index writers.
    - Impose items before write limits search index writer.
    - Sort comics by path for the reader navigation when in Folder View.
    - Remove inappropriate vertical scroll bars from page images.

## v1.2.5

- Features
    - In Folder View the reader navigates by folder instead of series.
- Fixes
    - OPDS crash on missing 24 hour time setting input required.

## v1.2.4

- Features
    - User configurable 24 hour time format.
    - Reader
    - Displays covers as one page even in two page mode.
    - Read in Reverse mode.
    - Keymaps for adjusting page by one page in two page mode.
    - Previous and Next book navigation buttons and keymaps.
- Fixes
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

- Fixes
    - Prevent search indexing starting over if it encounters errors.
    - Fix download buttons.
    - Fix admin settings drawer obscuring small screens.
    - Fix scroll bars showing inapproporately on admin tables.
    - Fix OPDS authors having 'i' appended.

## v1.2.2

- Fixes
    - Fix all items removed from search index after update.
    - Speedups to cleaning up search engine ghosts.

## v1.2.1

- Fixes
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
- Fixes
    - Some Librarian Status messages would appear never to finish.
- Development
    - The multiprocessing method is now S P A W N 💀 on all platforms.
    - Websockets are now handled by customized Django channels
    - aioprocessing Queue communicates between librarian and channels.

## v1.1.6

- Fixes
    - Fix rare deletion and recreation of all comics when inodes changed.

## v1.1.5

- Features
    - Admin Stats tab
    - Libraries can have a poll delay longer than 1 day.
- Fixes
    - Crash when removing comics.
    - Admin Create & Update dialogs would get stuck open on submit.
    - Delete expired and corrupt sessions every night.
    - More liberal touch detection for more devices.

## v1.1.4

- Fixes
    - Multiprocessing speedup for large search engine indexing jobs
    - Writes search engine data in segments.
    - Search engine segment combiner optimizer runs nightly (and manually).

## v1.1.3

- Fixes
    - Fix some OPDS browsers unable to read comics.

## v1.1.2

- Fixes
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
- Fixes
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
    - To ToxicFrog, who's been finding most of these bugs I'm fixing for a
      while.

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
    - Remove vestigial browser scrollbars when they're not needed. Thanks to
      ToxicFrog.
    - Fix cover cleanup maintenance task.

## v0.10.2

- Fixes
    - URLS dictate view over top group. Fixes linking into views.
    - Fix possible cover generation memory leak.
    - Build a deadfall trap for search indexer zombies. Use Offspring's brains
      as bait.

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
    - Use codex config namespace (\~/.config/codex) so codex doesn't interfere
      with standalone comicbox configs.
    - Comic issue numbers display to two decimal points instead of using ½
      glyphs.

- Features
    - Filename order by option. Disabled if the "Enable Folder View" Admin Flag
      is off.

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

- Fixes
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

- Fixes
    - Fixed combining CBI credits with other format credits
    - Failed imports notification appears only for new failed imports.

- Features
    - Update search index daily.
    - Clean up orphan comic covers every night.

## v0.9.8

- Fixes
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

- Fixes
    - Coerce decimal values into valid ranges and precision before importing.

- Features
    - Clean up unused foreign keys once a day instead of after every import.
    - Clean up unused foreign keys librarian job available in admin panel.

## v0.9.6

- Fixes
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

- Fixes
    - Fixed crash when importing comments metadata.

## v0.9.3

- Fixes
    - Import credits data for CBI and CIX tagged comics.
    - More liberal metadata decimal parsing.

## v0.9.2

- Fixes
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

- Fixes
    - Fix integrity cleanup check for old comic_folder relations that prevented
      migrations.

## v0.7.4

- Fixes
    - Fix integrity cleanup check for more types of integrity errors that may
      have prevented clean db migrations.
    - Fix last filter, group, sort not loading properly for some new views.

## v0.7.3

- Fixes
    - Fix crash updating latest version.
    - Fix a folder not found crash in folder view.
- Features
    - Database indexing speedups.

## v0.7.2

- Fixes
    - Fix another integrity check bug

## v0.7.1

- Fixes
    - Fix and integrity check crash that happened with an older databases.
- Features
    - Added `CODEX_SKIP_INTEGRITY_CHECK` env var.

## v0.7.0

### Feels Snappier

- Database Migration
    - v0.7.0 changes the database schema. Databases run with v0.7.0+ will not
      run on previous versions of codex.

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
    - Use TZ and TIMEZONE environment variables to explicitly set server
      timezone.
    - Added `VERBOSE` logging level to help screen out bulk `DEBUG` messages
      from dependencies.
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
    - Vacuum the sqlite database once a day to prevent bloat
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

- Fixes
    - Fixed intermittent Librarian startup crash in docker.
    - Fixed DEBUG environment variable to be able to run in production.
- Dev
    - Added DEV environment variable for dev environment.

## v0.6.1

- Fixes
    - Fix librarian startup crash. Prevented admin actions from happening.

## v0.6.0

### Better Filtering and Sorting

- Features
    - New Filters
    - New sort options: Updated Time and Maturity Rating
    - New frontend URL scheme
    - New API
    - Added time to the browse card when sorting by time fields
    - Browser pagination footer now remains fixed on the page
    - Browser pagination footer is now a slider to handle larger collections
    - Notifications now appear in reader as well as browser
    - On comic import failure, log the path as well as the reason
    - Codex version information moved to Browser > Settings
- Fixes
    - Fixed a bug importing Story Arc Series Groups and Genres. Requires
      re-import to correct.
    - Fixed a bug with sorting that grouped improperly and showed the wrong
      covers for reverse sorts.
    - Scanning notifications on login not disappearing bug squashed
    - Fixed a bug where the browser settings menu wouldn't close when opening a
      dialog

## v0.5.18

- Fixes
    - Fix filters not changing display bug

## v0.5.17

- Fixes
    - Fix root_path not parsing bug

## v0.5.16

- Fixes
    - Fix broken startup when parsing json shared between front and back end

## v0.5.15

- Features
    - Metadata popup is now faster.
    - Metadata popup now shows created_at, updated_at and path (if admin).
    - Removed numeric and common password validators. Made the minimum length 4.

## v0.5.14

- Features
    - Metadata view for browse containers. Also observes filters.
    - Covers now regenerate on re-import.

- Fixes
    - Fix scanning notification
    - Fix unable to delete libraries bug

## v0.5.13

- Features
    - Admin Flag for automatically updating codex
    - Force updates from the admin panel with an Admin Flag action
    - Snackbar for notifying about failed imports

## v0.5.12

- Features
    - Admin page for failed imports
    - Snackbar tells admins when scans are happening
    - Report the latest version available in the browser footer tooltip
    - Admin flag for disabling codex for non-users

## v0.5.11

- Features
    - Browser rows now adapt to browse tile size
    - Browser covers for containers now match data we're sorting by
    - Serve static files faster
- Fixes
    - Reader fix settings for all comics were not setting properly
    - Fix bookmarks for sessions that aren't logged in

## v0.5.10

- Fixes
    - Fix filtering bugs
    - Fix mark read/unread bugs
    - Fix reader settings not setting properly
    - Fix reader images positioning
    - Fix minor crash closing books with uninitialized browser app

## v0.5.9

- Fixes
    - Fix sorting for folder view
    - Fix import bugs
- Features
    - Display sort key value in browse tile
    - Display standard image for missing covers
    - Slightly more helpful 404 page

## v0.5.8

- Upload mistake with 0.5.7. This is just a version bump.

## v0.5.7

- Fixes
    - Fix import crashes
    - Remove scan locks on startup

- Features
    - Allow credits with an empty role
    - Pagination of large browse results
    - Center comic pages better
    - Add download link to browser menu
    - Log to files as well as console

## v0.5.6

- Fixes
    - Websocket path security wasn't handling leading slashes well. Skip it.

## v0.5.5

- Fixes
    - Revert to whitenoise 5.1.0 which works with subpaths

## v0.5.4

- Fixes
    - Fix crash on start if all static dirs do not exist.

## v0.5.3

- Fixes
    - Fixed login bug introduces in v0.5.3 (thanks hubcaps)
    - Fixed filtering bug introduced in v0.5.2
- Features
    - Versioned API
    - Toast popup for admins indicating libraries are scanning.
    - Periodic frontend refresh during long scans.
    - Codex version displayed in browser footer

## v0.5.2

- Features
    - Lazy load filter choices when the menu opens
    - Documentation moved into admin panel
- Fixes
    - Fix multiprocessing for Windows

## v0.5.1

- Minor bugfixes.

## v0.5.0

### First useful working version

- Productionized alpha release

## v0.4.0

### Polished UI

- Polished VueJS frontend

## v0.3.0

### I'm a frontend developer!

- Single Page VueJS frontend PoC without much styling

## v0.2.0

### It's alive

- Working application with all initial features
- Django frontend

## v0.1.0

### Hello world

- Proof of concept.
