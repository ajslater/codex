# 📜 Codex News

<img src="codex/img/logo.svg" alt="Codex logo" style="
height: 128px;
width: 128px;
border-radius: 128px;
" />

## v2.5.8

### ✨ Added

- New `Add Library` server folder picker component.

### 🐛 Fixed

- A new visitor's first page load no longer sometimes fails.
- Unchecking every default metadata format no longer breaks online tagging.
- Unreadable folders in Add Library say "Permission denied" instead of "Server
  Error".

## v2.5.7

### ✨ Added

- Series end year, status and summary are written to MetronInfo v1.2 and read
  back from it, no longer saved in Codex only.
- Metron online tagging uses only an API key; saved Metron usernames and
  passwords are removed.

### 🐛 Fixed

- Reader no longer jumps to the cover or the next book after a library update,
  or rewrites the bookmark of the book it leaves.
- Languages with a region or script, like pt-BR, are kept and shown by name.
- Admin explains why you can't remove your own staff or active status instead of
  showing an unknown error.
- The Metron response cache starts over once after upgrading.

## v2.5.6

### ✨ Added

- Filter, search, view, edit, and online tag by series years, series status, and
  series summary. End year, status and summary are saved in Codex only, not
  comic metadata.
- Browser title shows series years and a Tags button.
- Online tag match picker shows series and issue details to help disambiguate
  similar covers and titles.

### 🐛 Fixed

- Browsing comics without embedded tags, or re-importing unchanged comics, no
  longer rebuilds their covers and reloads the page.
- Searches for a universe designation no longer miss imported comics.

## v2.5.5

### ✨ Added

- `csrf_trusted_origins` setting for CSRF 403s behind a reverse proxy.
- Docker images now use Python 3.15

### 🐛 Fixed

- Online tagging matches saved for review by 2.5.3 no longer break the review
  list and scan status with "No module named 'numpy'". They are dropped, so
  those comics need tagging again.
- Renamed comics no longer contain colons or other characters Windows and SMB
  shares can't store.
- A Metron API key is no longer overridden by a `~/.netrc` login.

## v2.5.4

### ✨ Added

- Online tagging matches to review show a toolbar Review button and a tab-title
  count instead of popping up a dialog.

### 🐛 Fixed

- Escape in a reader dialog no longer closes the book, and keys typed in a
  dialog no longer turn pages.

## v2.5.3

### ✨ Added

- Online tagging gains an Ask match mode that prompts for every match instead of
  writing any.
- Admin Doctor tab: archive tools, PDF support, image codecs, database,
  libraries, watcher limits, config and package problems, each with its fix.
  Problems are also logged at startup.

### ♻️ Changed

- Docker image is about 165 MB smaller.

### 🐛 Fixed

- A missing or broken unrar no longer hides CBR comics from scans or deletes
  them from the library; they are listed as failed imports with the cause.
- A broken PDF library disables PDF reading instead of stopping the server.
- Metron logins by username and password tag again; a blank API key no longer
  overrides them.
- Credential checks no longer compete with a running tagging job for Metron's
  rate limit.
- Re-applying a chosen online match reuses the cached search.
- Failed imports no longer vanish from the admin list after other imports.
- Size searches accept kb, mb, gb and tb units and the >= and <= operators.
- Codex shuts down cleanly on Python 3.12 and 3.13.

## v2.5.2

### ♻️ Changed

- Docker image is about 490 MB smaller and starts faster.

### 🐛 Fixed

- Fresh PyPI installs no longer fail to start.

## v2.5.1

### ✨ Added

- Saved views can be deleted.

### 🐛 Fixed

- Browsing a series or volume emptied by tagging returns to the top instead of a
  list with no way back.
- Clearing a search or loading a saved view no longer leaves a list with no way
  back, and saved views keep their top collection.
- The saved views menu no longer reopens after loading a view.

## v2.5.0 - Admin Defaults

### ✨ Added

- Admin Defaults tab sets the browser and reader settings new sessions start
  with, replaces Default View, and can update existing anonymous sessions.
- Browser and reader resets restore the admin defaults.
- Read comics and collections show a check mark instead of dimmed titles.
- Online tagging match review shows each file's own cover beside its name.

### 🐛 Fixed

- A Folders or Story Arcs default view opens there instead of Publishers.
- Reader zoom scales pages from their original size.
- Fit to Screen fits wide pages when PDFs render as vectors.
- Admin tables and tag write errors no longer revert to old values.
- The reader's "b" shortcut sets bottom to top reading.
- "Clear All Filters" no longer shows when no filter is set.
- Anonymous browsing no longer logs a timezone error.

## v2.4.3

### 🐛 Fixed

- Comics you are reading no longer leave your unread list when another user
  finishes them.
- OPDS "Keep Reading" lists only issues in progress.
- OPDS reading position responses follow the Progression spec.
- Upstream widget bug fix accepted and released. Revert our fix here.

## v2.4.2

### 🐛 Fixed

- OPDS clients that send no login or session cookie can read reading positions
  instead of getting a 404 for every comic.
- Cover cards no longer say "100% read" or "0% read" on a comic that is partly
  read.

## v2.4.1

### 🐛 Fixed

- The browser pane was unable to scroll due to an upstream widget bug.

## v2.4.0 - Read State & Match Review

### ✨ Added

- Cover cards show read, unread, and in progress state.
- Online tagging match candidates show a cover, a link to the source's page, and
  what separated their scores.
- Hovering a match candidate's cover shows it full size.
- The Failed Imports link stays in the admin sidebar while there are failed
  imports.
- Admins can see and manage comics that disappeared from a library but have not
  been deleted yet.

### ♻️ Changed

- Browsing with tag filters is about twice as fast.

### 🐛 Fixed

- A filesystem outage no longer costs a library its comics, read progress, or
  custom covers.
- A comic that disappears from a library is kept for a day before it is really
  deleted.
- Two libraries whose paths overlap no longer destroy each other's comics and
  bookmarks.
- Moving, renaming, or force updating a comic keeps its read progress.
- Comics with uppercase file extensions no longer lose their folders and read
  progress.
- Read progress can no longer be recorded twice for the same comic.
- Folder, series, and story arc progress and read state are counted correctly,
  including while filters are active.
- Marking a comic or collection unread clears its progress.
- Breadcrumbs, metadata, and collection totals no longer name or count comics
  from libraries you can't see.
- Metadata imports and reading positions respect library and age-rating
  permissions.
- Browsing to a collection you can't see sends you up a level instead of a blank
  page.
- A comic whose file is missing or unreadable returns Not Found instead of a
  server error.
- OPDS clients can browse from the catalog root again, and one unreadable comic
  no longer empties a feed.
- The OPDS urls dialog opens, and its copy buttons work over plain http.
- Deleting a library succeeds, and library and group membership changes refresh
  the browser.
- A refused tag write names the comic to edit instead, and links to it.
- The metadata editor no longer saves values its own fields flag as invalid.
- Online tagging releases its Comic Vine connections when a scan finishes.
- The match review dialog no longer clips its Pause button, and the tagging
  connection chip shows its check or alert icon.
- Registration and the change-password dialog enforce the minimum password
  length.
- Invalid admin settings values are rejected instead of breaking browsing, and
  admin forms show the server's reason when a name is already taken.
- Clearing part of a poll interval no longer produces an invalid value, and the
  email host field accepts hostnames without a dot.
- The nightly cleanup keeps custom cover thumbnails and removes bookmarks
  belonging to no user or session.
- Panels gets both its own sort menu and the sort folders, on every platform.
- An installed Codex gets a dark app bar, and buttons on the orange accent use
  dark text.
- Browser cards draw their hover border, and cover thumbnails in table mode and
  on the custom-covers admin tab open with the keyboard.

## v2.3.3

### ✨ Added

- Codex now identifies itself in the requests it makes to Metron and Comic Vine.
- The end of a tagging session logs what it spent.
- The Tagging tab's per-source rate now shows the limit the server actually
  reported, not the documented default. A Metron donor tier or a self-hosted
  instance reads its own pace.

### 🐛 Fixed

- Answering an online-tagging match prompt now tags every issue of the series it
  was asked about, instead of one.
- The match-review dialog closes when the queue empties instead of showing a
  spinner, says how many comics a pick will write, and reopens from a Review
  button on the Tagging tab.
- A tagging run that exhausts the day's Metron quota now pauses and stays
  resumable.
- The vertical reader could miss the end of a book when scrolled by a fast
  fling.

## v2.3.2

### 🐛 Fixed

- The nightly maintenance run happened dozens of times a night instead of once.

## v2.3.1

### 💥 Breaking Changes

- Docker Hub users: `docker.io/ajslater/codex` is published again, but it is
  deprecated. Change your image to `ghcr.io/ajslater/codex`; nothing else
  changes. Admins see a warning in the web UI, and the logs warn at startup and
  once a day, until the image is changed. Coming from 1.9.x, back up your
  `config` directory first and read the Upgrading notes for every version since.

### ♻️ Changed

- Comic Vine tagging spends half the API budget it used to due to simyan 4.1.0.

### 🧑‍💻 Developer

- Require simyan >= 4.1.0.
- Resume publishing images to Docker Hub to upgrade stragglers.

## v2.3.0 - Reprints & Comicbox 5

### 💥 Breaking Changes

- Comicbox 5.0.0 reads some tags differently and adds others. Existing comics
  keep the tags they were imported with until they are read again: select comics
  and Force Update Tags, or let a scan pick up files you change. Until then the
  new fields are empty, and age ratings and credit roles keep their old
  spellings, so a filter can list both `Everyone 10+` and `Everyone`, or both
  `CoverArtist` and `Cover`. Age-restricted access is unaffected either way.

### ✨ Added

- Sort by Reprints, the other editions an issue was published as, in the table
  and in cover view. Filter by a reprint first to sort by that one.
- Read a reprint series as a reading order from the reader's reading-order menu,
  which makes reprint tags usable as durable reading lists.
- "Alternate Series" is now "Reprints" everywhere: it covers MetronInfo Reprints
  and AlternativeNames, ComicInfo AlternateSeries and CoMet isVersionOf. A
  series' other names are listed separately in the metadata panel.
- Each top collection remembers the sort it was last browsed with, and clearing
  a search puts back the sort it replaced.
- Manga is its own tag now, separate from reading direction, along with
  MetronInfo's Manga Volume.
- A comic's own web links are shown and editable.
- Credits mark the primary holder of each role and list them first. Codex cannot
  write it back: neither ComicInfo nor MetronInfo stores it.
- Online tagging takes an Effort setting, per scan and as an admin default.
  Thorough restores Comic Vine's unbounded search, Minimal trades matches for
  speed, and Metron ignores it. Auto, the default, drops a large unattended scan
  to Minimal so Comic Vine's hourly limit doesn't stretch it into hours.
- The tagging status strip shows Comic Vine's remaining hourly budget.

### ♻️ Changed

- Web requests share a pool of database connections instead of opening one each.
  `db_workers` under `[server]` sizes it, or turns it off with 0.

### 🐛 Fixed

- Reading Bottom to Top jumped to the wrong page: page one showed the last page.
- Saving browser settings sent an empty request. The next page request saved
  them anyway, so nothing was lost.
- Sorting by a tag column outside the table view no longer errors.
- Browsing a group whose parents have gone missing shows a button back to the
  top rather than an empty crumb trail and no way out.
- The Admin Tagging Status table shows what is being looked up right now.
- Identifier links are built from the id instead of stored beside it, so they
  can no longer disagree with it. A comic can carry an id for its series, and a
  reprint's id links to the issue it reprints. The tag editor writes identifier
  types the way the formats spell them.
- A Comic Vine key the site rejects now fails validation instead of passing.
- Comicbox's online caches stay under the config directory instead of a location
  that recreating a container discards.
- An online scan's time estimate is keyed on Effort rather than Match Mode,
  which never changed how many requests a comic costs. It reads higher, and a
  real scan beats it.
- Covers are cached by the browser and revalidated instead of re-sent, so
  revisiting a page does not download them again. They also survive a scan,
  which used to discard every cached cover whether or not it had changed.
- Every web request leaked a database connection, and its open files, until
  garbage collection.

### 🧑‍💻 Developer

- Comicbox 5.0.0, and its metadata schema v3.0.
- Simyan, mokkari and requests-cache are declared directly rather than relied on
  through comicbox.
- Asgiref is declared directly; the connection pool uses its executor registry.

## v2.2.11

### ✨ Added

- Edit a comic's publish date in the tag editor. Year, month and day are
  separate, so a year-only comic stays that way. Editing a date rewrites the
  whole date tag: a MetronInfo StoreDate does not survive it, and a multi-comic
  edit overwrites parts they disagree on.
- Country, Collection Title and Alternative Issue are editable too, having only
  ever been displayed.
- Redesigned the Admin Tagging Status table to be more informative.

### 🐛 Fixed

- Bookmarks and read progress survive tag writes. Comics are renamed before they
  are written and the database moves with the file, so a rename, a CBR
  conversion, or a library scan landing mid-batch can no longer lose them. PDFs
  lost them every time before; other formats occasionally.
- Comics are no longer deleted while their files are still on disk. One replaced
  in place, by a tool that removes and rewrites it, is re-read instead of
  deleted and re-added as a new comic.
- A library that has gone missing, like an unmounted share or volume, no longer
  has all of its comics deleted.
- Paths that merely begin the same way are no longer confused for one another:
  deleting the folder "Batman" leaves "Batman Beyond" alone, and libraries at
  /comics and /comics-kids no longer claim each other's changes.
- Renaming keeps each archive's own file extension. PDFs and unconverted CBRs
  were renamed to .cbz names.
- Two comics that would end up with the same filename no longer overwrite each
  other; the second is reported instead.
- Editing a comic's tags twice in a row no longer fails the second time with a
  "no such file" error.
- Online tagging only offers Resume when a scan can actually resume, and reports
  a failed pause or resume instead of silently doing nothing.
- A second online tagging scan no longer re-queues comics the running scan
  already has.
- Deleting a folder refreshes the series and publishers it emptied, which kept
  listing comics that were gone.
- The librarian shuts down cleanly with work queued, and tasks queued in the
  same instant no longer collide and lose one.

## v2.2.10

### 🐛 Fixed

- Fix a rare crash opening RAR3 extended timestamps with CBR files.

## v2.2.9

### 🐛 Fixed

- OPDS responses are cached per client User-Agent. Clients that support
  different features no longer receive each other's cached feeds for a minute.
- OPDS v1: comic credits that are not writing credits, like artists and
  colorists, appear as contributors in metadata feeds. They had never been sent.
- OPDS: Panels on iOS (3.13 and later) is recognized as a facet capable client
  and receives real OPDS facets, shown in the native filter menu, instead of
  sort options faked as navigation folders. The macOS build (951), which does
  not support facets, keeps the navigation folder sort options.
- OPDS v1: facet capable clients like kybooks no longer also receive a dead,
  unclickable duplicate entry for every facet alongside the real facet links.
- OPDS v1: facet groups are labeled "Order By", "Order Direction" and "Views"
  instead of the internal query parameter names clients displayed verbatim, like
  "orderBy".

## v2.2.8

### ✨ Added

- Docs for passing through the Server: HTTP header so codex may be identified by
  OPDS clients like Stump.

### 🐛 Fixed

- Codex updates itself again, automatically or on demand, and announces new
  versions.

## v2.2.7

### 🐛 Fixed

- A comic moved or renamed onto a path that already belongs to another comic,
  like a duplicate landing in a dupes folder, no longer crashes the scan and no
  longer crashes every scan after it. The stray move is skipped and the leftover
  record is cleaned up by a later scan.

## v2.2.6

### ✨ Added

- The Comic Vine custom URL is back, for tagging against a Comic Vine proxy or
  mirror. URLs discarded by v2.2.4 must be entered again. Metron Cloud's stays
  gone; it never did anything.

## v2.2.5

### ✨ Added

- Online tagging combines search and tag by id. A source given an issue id
  fetches it directly, the rest search, and the results merge (comicbox 4.8.0).

### 🐛 Fixed

- Tagging a comic with renaming enabled no longer fails the import and discards
  the new tags. Comics renamed this way since v2.1.0 need a Force Update Tags to
  pick up their metadata.
- Comics renamed or moved by another program mid-scan no longer leave a
  permanent failed import.

## v2.2.4

### ✨ Added

- Metron Cloud online tagging uses an API key, generated on your metron.cloud
  account page (comicbox 4.7.1). Saved usernames and passwords keep working
  until you save a key, which replaces them.
- The custom URL fields for Metron Cloud and Comic Vine are removed. The Metron
  one never did anything — mokkari hardcodes the metron.cloud endpoint. Any
  saved URLs are discarded on upgrade.
- The interactive Swagger API docs are back, at `/api/v4/`. They went away in
  v2.0.0 with the v3 API; only the raw OpenAPI schema at `/api/v4/schema`
  remained. Admin login required, as before.

## v2.2.3

### ✨ Added

- Alternate series names: the localized and variant series titles comics carry
  in MetronInfo AlternativeNames and Reprints tags (and that Metron and Comic
  Vine online tagging now record) are imported, shown in the metadata panel,
  editable in the tag editor, and browsable — sort, table column, filter, and
  `alternate_series:` search (comicbox 4.6.0). Comics imported or tagged online
  from now on pick them up automatically; already-imported comics need a Force
  Update Tags.
- Online tagging matches a comic filed under a localized or variant series title
  to the right volume, and the match prompt shows each candidate's other known
  names (comicbox 4.6.0).

### 🐛 Fixed

- Identifier links point at the right page. Hand-tagged keys with a type prefix
  like `series:178012`, Comic Vine long codes like `4050-160294`, and
  `source:type:key` strings made broken issue-shaped URLs for every source
  (comicbox 4.6.1).
- Every identifier URN in a comic's notes is imported; only the first was read
  before (comicbox 4.6.1).
- Story arcs tagged online from Metron or Comic Vine get web links (comicbox
  4.6.1). These identifier fixes reach already-imported comics on their next
  re-import, or use Force Update Tags.
- User data backups no longer skip every saved filter set after an upgrade that
  adds a new filter.

## v2.2.2

### 🐛 Fixed

- Clearing a field in the tag editor now removes it from the comic's tags.
  Cleared fields were silently left unchanged in the archive (comicbox 4.5.0).
- The tag editor's Monochrome checkbox reads and writes again, and clearing it
  removes the tag instead of marking the comic color (comicbox 4.5.1).
- PDF pages scanned upside down or sideways and righted by the pdf's rotation
  attribute displayed rotated when the reader served them as images
  (comicbox-pdffile 0.6.3).
- Reading a PDF that needs in-memory repair no longer rewrites the file on disk
  (comicbox-pdffile 0.6.3).
- PDFs no longer count an embedded metadata file as a page (comicbox 4.5.0).
  Imported PDFs correct themselves on their next re-import, or use Force Update
  Tags.

## v2.2.1

### ✨ Added

- Community ratings: the average and vote count comics carry in their tags (and
  that Metron online tagging now fetches) are imported, shown in the metadata
  panel, editable in the tag editor, and browsable — sort, table column, filter,
  and `community_rating:` search (comicbox 4.4.0). Existing critical ratings
  become community ratings automatically; they always came from the same tags.
- Alternative issue numbers are imported and shown in the metadata panel
  (comicbox 4.4.0).
- Testing Metron credentials in the Admin panel now shows your account's live
  rate limits; the daily limit reflects your Metron donor tier.
- The online tagging status table shows Metron's live daily budget as a run
  progresses.
- Metron rate limits now come from your account instead of fixed defaults;
  donor-tier limits are picked up automatically (comicbox 4.3.0).

### 🐛 Fixed

- Online tagging backs off properly when a rate-limited response omits a retry
  hint (comicbox 4.3.0).

## v2.2.0 - Single Sign-On

### ✨ Added

- Single sign-on: log in through an OIDC identity provider such as Authentik or
  Authelia, configured in the Admin panel's new Auth tab. Optionally auto-create
  users, sync identity-provider groups to Codex groups, and grant admin from a
  group.

### ♻️ Changed

- ComicVine online tagging estimates rate-limit waits more accurately, hangs
  less, and cleans up stale cached responses automatically (comicbox 4.1.1).

### 🐛 Fixed

- Answering an online-tagging match prompt now writes to the comic's current
  file even if it moved since the scan, and reports apply failures instead of
  silently dropping the match.
- The configured log level is now honored while reading and writing comic
  metadata.

## v2.1.2

### 🐛 Fixed

- A folder with denied permissions no longer crashes the whole library scan.
- Ignore NAS and OS junk folders, including Synology recycle bins and macOS and
  Windows metadata.

## v2.1.1

### ♻️ Changed

- Metron online tagging makes far fewer API requests (comicbox 4.0.5).

### 🐛 Fixed

- Fix unable to change password.

## v2.1.0 - Renaming

### ✨ Added

- Rename comic files to the comicbox naming scheme when editing tags or tagging
  online.

### 🐛 Fixed

- Online tagging matches already-tagged comics more accurately by searching
  embedded metadata instead of the filename (comicbox 4.0.4).
- Renaming a file no longer fails when a series or title contains a slash
  (comicbox 4.0.4).
- Clearing a search returns to the top collection instead of stranding you at a
  lower level.

## v2.0.5

### 🐛 Fixed

- Admin user password changes no longer fail with an unknown error.

## v2.0.4

### ✨ Added

- Add Sweet Shop kebab case filename format. Courtesy of @bpepple.

### 🐛 Fixed

- Online cover matching now works for PDFs; the cover page is rasterized before
  perceptual hashing instead of handing raw PDF bytes to the image hasher.
  Courtesy of @bpepple.
- Security release for dependencies.

## v2.0.3

### ✨ Added

- Libraries can be marked read-only to protect their comic files from tag
  changes. Read-only comics hide their Edit Tags and Online Tagging buttons, and
  bulk edits spanning several libraries skip them.

### 🐛 Fixed

- CBR comics with high-precision file timestamps no longer fail to import
  (comicbox 4.0.2).

## v2.0.2

### 🐛 Fixed

- The web UI now works under a reverse-proxy subpath: the live-update websocket,
  API calls, and cover images honor `url_path_prefix` instead of loading from
  the server root.

## v2.0.1

### 🐛 Fixed

- The Online Tagging Status table now shows which source matched each comic,
  even ones re-tagged from a stored id or matched by both sources.
- Tidied the Online Tagging Status table: long filenames use the full Comic
  column width before truncating.
- Re-tagging an already-identified comic now fetches its exact Metron or Comic
  Vine issue directly instead of running a full search.
- Tagging no longer loses a comic's stored Metron or Comic Vine id when it also
  has a web link.
- `url_path_prefix` works again when set without a leading slash. Remember to
  uncomment the \[server] block header in codex.toml if you are setting server
  values, like \`url\_path\_prefix\`\`

## v2.0.0 - Tag Editing & Online Tagging

### 💥 Breaking Changes

- This is a major upgrade. A one-time database migration runs on first startup;
  back up your `config` directory before upgrading.
- Editing tags writes to your comic files; the comics directory must be mounted
  writable with write permission for tag editing to work.
- Admin settings (SMTP, rate limits, browser page size, cover upload size) moved
  from `codex.toml` into the Admin UI and are now editable without a restart.
  Existing values are imported automatically on upgrade; those `codex.toml`
  sections are deprecated.
- Custom covers are now managed in the web UI. Legacy filesystem covers
  (in-library `.codex-cover.*` files and the covers-only library) migrate
  automatically on first startup.
- The browser and reader page URLs changed; bookmarks to specific pages may need
  re-navigating from the home screen. OPDS apps reconnect on their own.
- The HTTP API moved from `/api/v3/` to `/api/v4/`.

### ✨ Added

- Edit the tags on one or many comics directly in the browser — credits, story
  arcs, identifiers, and more — written back to your comic files.
- Online tagging: look up and apply metadata from online sources, with
  interactive match prompts, rate-limit display, and per-source credentials in
  the new Admin Tagging tab. Or tag a single comic directly by a known Metron or
  Comic Vine issue id or URL, skipping the search.
- Upload, replace, and remove custom covers for any group from the web UI, plus
  a Custom Covers admin tab.
- Back up and restore all user data — accounts, bookmarks, favorites, settings,
  libraries — via a `user_data.sqlite` sidecar, the Admin Restore tab, or
  `codex restore_user_data`. Snapshotted nightly.
- Optional self-service password reset, and email verification for new sign-ups
  (both require SMTP).
- New user Profile dialog for self-service username, email, and API token (moved
  here from the sidebar).
- Database and user-data backups are now compressed, dated, and auto-pruned.
- Redesigned admin panel has moves settings under relevant tabs.

### ♻️ Changed

- Library imports are faster: forced re-imports run over 20x faster, fresh
  imports almost 4x, and polls that find nothing changed are now nearly instant
  — no more rewriting every comic, regenerating every cover, and refreshing
  every browser on a no-op poll.
- Browsing large libraries is faster: table, search, and sorted folder views
  that could take minutes now load in about a second, metadata works on
  collections of any size, and browsing stays responsive during imports.

### 🐛 Fixed

- OPDS 1.2, 2.0, and OpenSearch feeds are now spec-compliant.
- Folder covers respect favorites.
- Critical ratings normalized to a consistent 0–5 scale.
- The age-rating "As Tagged" panel hides when it has no entries.
- Hovering a comic's tag icon no longer re-runs the on-demand tag importer
  forever on comics with few or no embedded tags.
- Browser refreshes more often when comics change. container restarts.

## v1.12.8

### 🐛 Fixed

- Fix read/unread filter leaking one user's read state to other users.

## v1.12.7

### 🐛 Fixed

- Fix folder custom covers.
- Fix AUTH\_REMOTE\_USER for api endpoints.

## v1.12.6

### 🐛 Fixed

- Admin panel and other lazy-loaded routes broken.

## v1.12.5

### ✨ Added

- Select by range in multi-select with shift+click.

### 🐛 Fixed

- Fix "Last Read" column in table view crashing.
- Ignore dotfiles.

## v1.12.4

### ✨ Added

- Force Update Tags by individual group.

### 🐛 Fixed

- Crash on Cleanup Favorites Janitor Job.

## v1.12.3

### ✨ Added

- Add touch swiping back to the reader with an implementation that's less
  twitchy than before.

### 🐛 Fixed

- Fix scroll bar controls appearing on the Edge browser in tags screen values.

## v1.12.2

### 🐛 Fixed

- Ordering in browser card mode was broken for groups

## v1.12.1

### ✨ Added

- Fail2Ban support with a dedicated log. See README.

### 🐛 Fixed

- Comic filename parsing improvements.
- Downgrade noisy profile forbidden WARNINGS to DEBUG. They are a normal part of
  connecting.

## v1.12.0 - Browser Table View & Favorites

### ✨ Added

- Browser Table mode shows configurable, sortable, metadata columns.
- Favorite objects and filter on them.
- Serve image-dominant PDF pages as just their images.

## v1.11.5

### 🐛 Fixed

- Fix occasional recreation of comics on docker or network filesystems.
- Fix double polling of some libraries.
- Fix Codex sometimes hanging on shutdown after Ctrl+C.
- Fix PDFs rendering OCR overlay text.
- Fix PDFs sometimes not rendering at correct resolution

## v1.11.4

### 🐛 Fixed

- Fix extra horizontal scrollbar in browser on Firefox.

## v1.11.3

### 🐛 Fixed

- Fix several missing information chips in the tags view.

## v1.11.2

### 🐛 Fixed

- Browser had two scroll bars.
- Reader stopped scrolling to the top of the page on page turn.
- Reader setting Cache Entire Book now defaults to False.

## v1.11.1

### 🐛 Fixed

- Crash on anonymous user setting timezone

## v1.11.0 - Age Restrictions & Snappiness

### 💥 Breaking Changes

- This version of codex needs to re-sync the search index on first startup which
  make take time on large collections. However, the new search sync is faster
  than before.

### ✨ Added

- Age Rating Restrictions now available in the Admin Users tab.
- Admin Flag for defaulting to Folder View.
- The codex cache directory for covers and views may now have it's location
  configured.
- OPDS v2 alternate links for publications to external url identifiers.
- OPDS v2 publishers as proper contributors with links.
- OPDS v2 volumes in belongsTo

### ♻️ Changed

- Performance improvements across all views and batch jobs.
- Comicbox learned how to use multiprocessing & caching for importing.
- Cover thumbnail generation uses multiprocessing and seeds covers on import.

### 🐛 Fixed

- Clear stale `metron.cloud/{genre,location,story,tag,role}/...` URLs from
  existing identifiers — Metron has no public web pages for those types, so the
  links always 404.
- Fix full text search for credits, identifiers and story arcs.
- Fix OPDS v2 progression syncing response.
- Fix OPDS v2 belongsTo.position attribute.
- Database repairs itself before migrations.

## v1.10.15

### 🐛 Fixed

- Fix OPDS navigation going to wrong browser groups. Fix contributed by
  @beville.

## v1.10.14

### 🐛 Fixed

- OPDS auth challenges now include the WWW-Authenticate header and the
  application/opds-authentication+json Content-Type so clients like Panels
  reliably prompt for credentials.
- Various small frontend fixes

## v1.10.13

### 🐛 Fixed

- Fix PDFs not displaying with default reader settings.
- Fix browser paginator slider.
- Possible fix for expired and corrupt sessions causing FK errors.

## v1.10.12

### ✨ Added

- Codex identifies itself in the HTTP Server: header.
- Codex identifies itself in the OPDS v1 <generator> tag.
- Adjusted importer batching variable defaults for greater throughput

### 🐛 Fixed

- Fix an occasional bug linking folders when importing.
- Fix updating comics crash by batching comic updates.
- Fix possible import crashes in delete & linking.
- Fix overzealous lazy importer importing tags from books that already had tags.
- Fix reader settings clearing anomalies. Add a global reader settings clear
  button.
- Fix unnecessary redirect in OPDS when viewing comic in extended metadata.

## v1.10.11

### 🐛 Fixed

- Custom covers were not importing.
- Custom group covers were not counted in admin library view.

## v1.10.10

### 🐛 Fixed

- Fix creating non-extant reader global settings.

## v1.10.9

### 🐛 Fixed

- Fix browser settings not clearing with clear button.
- Fix search settings not clearing on OPDS start page.

## v1.10.8

### 🐛 Fixed

- Reset settings on OPDS start page more consistently.
- More logging for webserver errors.
- There's a jump in version numbers because the production build process was
  broken.

## v1.10.4-7 - Broken releases

## v1.10.3

### ✨ Added

- Select many mode in browser for browser actions.

### 🐛 Fixed

- Poll all libraries button was not polling all libraries.
- Fix OPDS v2 manifest series link.
- Force OPDS v2 start link to reset filters and order
- Library server folder picker shows folder menu more consistently.

## v1.10.2

### 🐛 Fixed

- Fix many OPDS v2 links leading to the wrong views.
- Fix admin update user validation.

## v1.10.1 - Mistaken release

## v1.10.0 - Rust modules & Settings Features

### 💥 Breaking Changes

- The docker repo has changed to ghcr.io/ajslater/codex
- Django 6 requires python >=3.12.
- Unified configuration
    - Your hypercorn.toml config will be migrated automatically to codex.toml.
      Options previously only configurable with environment variables may now be
      also be specified in codex.toml.
    - Some of the environment variable names have changed, but old values are
      still respected for compatibility.
- Replaced the thumbnail filename algorithm. Thumbnails will regenerate.

### ✨ Added

- Browser can save and load named views.
- Reader Settings are now available for Series, Parent Folder and Story Arc
- The Admin Jobs tab is an enhanced tasks tab with start and stop buttons and
  job progress.
- Browser Pane refreshes with a click/touch pull control.

### ♻️ Changed

- Codex now uses the Granian http server instead of Hypercorn.
- The file watcher and poller now use one thread each no matter how many
  libraries you have.
- Shaved about 80MB off the compressed docker image and 15MB off the python
  wheel.

### 🐛 Fixed

- Fix old dynamic covers displaying when database had changed due to imports.
- Fix erroneous "Bookmark" filter appearing in filter menu when a read state is
  selected.
- Fix reader close button receiving nonsensical route.
- Fix job status messages sometimes not being updated correctly.
- Fix check latest version of Codex bug.
- Tags page sometimes had erroneous links went nowhere.
- Fixed some foreign key integrity fixing bugs.

## v1.9.24

### 🐛 Fixed

- Fix OPDS v2 numberOfItems pagination sum.

## v1.9.23

### 🐛 Fixed

- Fix admin tasks tab crash
- Fix Library folder picker showing bad data

## v1.9.22

### 🐛 Fixed

- Fix many batch jobs not running. Including polling and importing.

## v1.9.21

### 🐛 Fixed

- Fix OPDS v2 manifest crash

## v1.9.20

### ✨ Added

- Browser filters now show selected filters more clearly in the menus.
- Fix filtering on credits when clicking on metadata chips.
- OPDS v2 credits and subjects now link to views filtered on the tag.

## v1.9.19

### 🐛 Fixed

- Fix PDF date parsing bug on import.
- Fix comic names with null volume\_to field.
- Provide volume name in comic title for OPDS v2 as there's no volume view
  available.
- Fix OPDS v2 folder as collection naming.

### 🧑‍💻 Developer

- Vuetify 4.0 frontend

## v1.9.18

### 🐛 Fixed

- Fix search indexing the universes tag.

## v1.9.17 - Broken build

## v1.9.16

### 🐛 Fixed

- Fix broken Reader close button.
- Fix OPDS v2 progression crash

## v1.9.15

### 🐛 Fixed

- Fix OPDS v2 progression crash.
- Adjust OPDS v2 progression position field to be 1 based, while Codex page is 0
  based.

## v1.9.14

### 🐛 Fixed

- Fix bad href validation in OPDS v2 leading to null links and therefore invalid
  OPDS.

## v1.9.13

### ✨ Added

- OPDS order by filename.

### ♻️ Changed

- Codex only accepts auth tokens prefixed with the Bearer header.

### 🐛 Fixed

- Fix crash on API schema generation.
- Fix scribe daemon not shutting down properly.
- Fix Swagger API docs crash.
- Fix full text search barfing on single quoted terms.
- Return 401 and authorization v1 json to OPDS instead of 403 on auth failure
  more often.

## v1.9.12

### 🐛 Fixed

- Fix accepting OPDS v2 progression correct Content-Type.
- Fix parsing OPDS v2 progression position.
- Fix bookmark update crash.

## v1.9.11

### 🐛 Fixed

- Fix OPDS v1 pagination.

## v1.9.10

### ✨ Added

- Allow "Bearer" header for token authentication in addition to "Token"

### 🐛 Fixed

- Fix Remote-User authorization for proxy setting http headers.
- Fix order links not appearing in OPDS v1

## v1.9.9

### ✨ Added

- Remote-User HTTP header SSO support activated by an environment variable. See
  docs.
- HTTP Header Auth Tokens are now accepted as authorization. Useful for OPDS and
  possibly some SSO setups.

### 🐛 Fixed

- Access control bug would let users see comics in include groups they were not
  a part of.
- Remove redundant top links from OPDS v2 facets group block.
- Fixed a status crash.

## v1.9.8 - Bad release, does not start

## v1.9.7

### 🐛 Fixed

- Fix OPDS v2 manifest/reading crash.
- Fix OPDS v2 search.

## v1.9.6

### 🐛 Fixed

- Fix OPDS feed crash.

## v1.9.5

### 🐛 Fixed

- Fix settings not resetting to default on OPDS start pages.
- Isolate OPDS settings from web settings so they don't reset each other.

## v1.9.4

### 🐛 Fixed

- Fix unnecessary redirects in OPDS v1 & v2 search.

## v1.9.3

### 🐛 Fixed

- Unnecessary redirect going to OPDS v1 start page.
- Fixed start page link in OPDS v2.0

## v1.9.2

### ✨ Added

- OPDS 1.0 gains a homepage similar to OPDS v2
- OPDS start page URLS are now different. See the OPDS popup dialog.

### 🐛 Fixed

- OPDS 2.0 homepage preview sections were showing the wrong queries.
- OPDS 2.0 progression bookmarking was broken. Stump doesn't seem to be
  transmitting progression data yet, though.

## v1.9.1

### 🐛 Fixed

- OPDS v2 fix crash on faceted views.

## v1.9.0 - OPDS 2.0 Redesign

### ✨ Added

- Redesigned OPDS v2 to work with Stump & Readest Clients
- Docker healthcheck endpoint. See docs.

### 🐛 Fixed

- Fix crash in OPDS v2 feed.

## v1.8.22

### 🐛 Fixed

- Fix reading books crash that crept into the last release.

## v1.8.21

### 🐛 Fixed

- Fix Close Book button linking to parent of desired route.

## v1.8.20

### 🐛 Fixed

- Fix dragging when zoomed in in reader when using mouse left button.
- Fix weird spacing and borders on browser and reader toolbars.
- Attempt to make Close Book route in reader more accurate.

## v1.8.19

### 🐛 Fixed

- Do not sanitize Library and Comic path names. Fixes an import crash on paths
  with dangerous looking strings in them.
- Fix a crash when moving comics.

## v1.8.18

### ✨ Added

- Read metadata from PDF embedded files.

### 🐛 Fixed

- Filter and Search parameters were being applied after clearing.

## v1.8.17

### ✨ Added

- Python 3.14 support.

### 🐛 Fixed

- Fix for codex sometimes shutting when asked to restart.

## v1.8.16

### ♻️ Changed

- Don't support Python 3.14 until dependencies do.
- Docker image is now based on trixie debian

## v1.8.15

### ♻️ Changed

- Replace axios with xior AJAX library.

## v1.8.14

### 🐛 Fixed

- Fix settings not saving in reader and sometimes in browser.
- Fix shutdown and restart signals on Windows.

## v1.8.13

### 🐛 Fixed

- Fix import crash when metadata import is disabled.

## v1.8.12

### 🐛 Fixed

- Fix publishers and series tags disappearing. Use Library Force Update to
  restore them.
- Fix credit role order in tags screen.

## v1.8.11

### 🐛 Fixed

- Restarting Codex with Codex would still crash. More comprehensive fix.

## v1.8.10

### 🐛 Fixed

- Restarting Codex with Codex would crash, so Auto-Update restarts were broke.
    - Sorry non-docker homies! Thanks @professionaltart.
- Fix universes not being search indexed (very rare).
- More reliable re-render for browser page slider and navigation buttons.

## v1.8.9

### 🐛 Fixed

- Attempt to fix not saving new stat values if update doesn't update comic
  metadata.
- Attempt to fix import bug where update metadata is disposed of before it can
  be applied.
- Attempt to fix browser page slider not updating to match the current folder.

## v1.8.8

### 🐛 Fixed

- Fix import crash on some Metron tagged comics with a primary identifier
  source.

## v1.8.7

### 🐛 Fixed

- Make Full Text Search table smaller. Some irrelevant fields and data were
  causing exponential bloat, crippling large libraries.
- Fix search by field for string fields, identifiers and issue.
- Fix overflow on browser card titles.

## v1.8.6

### 🐛 Fixed

- Scale search index sync batch size with memory. Large search sync query was
  preventing search sync of large databases on small machines.

## v1.8.5

### 🐛 Fixed

- Better fix for persistent settings. Old fix could lead to settings that never
  clear.

## v1.8.4

### 🐛 Fixed

- Fix not importing page\_count when import metadata is off, leads to unreadable
  books.
- Fix persistent settings.

## v1.8.3

### 🐛 Fixed

- Fix searching by string like fields in the search bar like 'path'.
- Fix minor search update exception when there's nothing search related to
  update on import.

## v1.8.2

### 🐛 Fixed

- Force docker logs (all stdout logs) to colorize output.

## v1.8.1

### 🐛 Fixed

- Fix minor search update exception.

## v1.8.0 - MetronInfo & CB7

### ✨ Added

- Support
  [MetronInfo.xml v1.0 Schema](https://metron-project.github.io/docs/category/metroninfo)
  for comic metadata.
- Support CB7 (7zip) comic archives.
- Search Indexing now also done in the import phase which is faster than syncing
  from the db:
    - 20k comics both imported and indexed in 9 minutes on my old macbook at a
      rate of 30 comics per second. Half a million comics might take less than 5
      hours on the same machine.
    - However this update replaces the search index and Codex will sync the
      search index when it starts.
- Fewer database updates when comics change metadata or don't change metadata at
  all means fewer and faster update imports.
- New Tags
    - Add Universes. Main Characters, and Main Team marked with a ★.
    - Metron tags can provide links to web databases for each tag.
- New Import Metadata on Demand Admin Flag.
- Add manual Import Abort task for admins.
- Browser tab titles show route and page title, no longer show custom banner.
- Logging format changed.

### 🐛 Fixed

- Reading Order in reader was not always defaulting to your last Browser Top
  Group.
- Fixed filtering on Critical Rating and FileType
- Fixed searching on Critical Rating field.
- Bug displaying Age Rating, Original Format, Scan Info, Tagger in metadata.
- Fixed database locking crashes.
- Attempt to fix major version change CSRF errors by forcing logout if CSRF
  errors occur.

### 🧑‍💻 Developer

- Uses Comicbox 2.0 see
  [Comicbox NEWS for all details](https://github.com/ajslater/comicbox/blob/main/NEWS.md)

## v1.7.15

### 🐛 Fixed

- Fix unable to change top group to folders or story arcs if on root browse
  page.

## v1.7.14

### 🐛 Fixed

- Fix Reader jumping back into the same book when changing to a new book.

## v1.7.13

### ✨ Added

- Experimental `CODEX_BROWSER_MAX_OBJ_PER_PAGE` env variable. Default is 100.

### 🐛 Fixed

- Fix Reader Reading Order dropdown unable to change reading order.
- Fix loading root browser pages greater than 1 as a new route.
- Missing books error screen had no toolbars, could not close it.
- Fix docker configuration for Synology by creating a comicbox config directory.
- Wait to load browser and reader pages until login tried with a cookie.

## v1.7.12

### ✨ Added

- Animate Pages option toggle in reader settings

### 🐛 Fixed

- Crash downloading comics when user is in a group.
- User last active activity was often not recorded.

## v1.7.11

### 🐛 Fixed

- Fix importing of story arc tags

## v1.7.10

### 🐛 Fixed

- Fix occasional import link tags crash.

## v1.7.9

### 🐛 Fixed

- Tags page layout fixes.

## v1.7.8

### ✨ Added

- Tags page layout changes with more notes from @beville.

### 🐛 Fixed

- Tags for simple comic fields were incorrectly taken from the first comic in a
  group.
- Filter menu wasn't populating for top folder.
- Librarian status tasks would appear out of order.

## v1.7.7

### 🐛 Fixed

- Fix Librarians Statuses not loading in UI.
- Tags screen crash with untagged series or volumes.
- Fix tags screen Mark Read confirmation names.
- Order Tags Contributors by relevance not alphabetically.

## v1.7.6

### ✨ Added

- Always Show Filenames setting for browser cards.
- Tags page layout changes with notes from @beville.

### 🐛 Fixed

- Fix import crash on files with escapable html characters or utf-8 chars in the
  filename.
- Fix page range crash in reader.
- Fix overzealous escaping of html in metadata strings.
- Fix group tags not aggregated properly in metadata screen for folders and
  story arcs.

## v1.7.5

### 🐛 Fixed

- More granular websocket notifications means the web UI does fewer more
  targeted data updates.
- Prevent deactivating and deprivileging the logged in user.
- Fix resetting active flag when resetting admin user with environment variable.
- Fix crash in auto-update when unable to determine current Codex version.

## v1.7.4

### 🐛 Fixed

- Fix setting bookmarks and book settings bug.
- Sanitize HTML out of imported comic metadata fields and admin inputs.

## v1.7.3

### ✨ Added

- Browser Order By Child Count.
- Customized site title option in Admin Flags.
- Codex logs are now compressed when rotated.
- Support OPDS v2.0 Progression (streaming) draft proposal from Aldiko.

### 🐛 Fixed

- Browser Group Mark Read/Unread obeys browser filters.
- Fixed bad redirect when to deep linking into browser Folders or Story Arcs.
- Fixed order by name for issues disregarding volume names in browser and reader
- Fix display of name and filename on browser cards.
- Fix batching import of Contributors to prevent crash on large imports.
- Fixed an OPDS Metadata crash.

## v1.7.2

### ✨ Added

- Download entire groups of comics from the browser and metadata screens.

### 🐛 Fixed

- Fix reader page API sometimes crashing.

## v1.7.1

### ✨ Added

- Always display filename for comics on browser cards in Folder View
- Detect .jxl extension (JPEG XL) as a comic page.

### 🐛 Fixed

- Fix ignoring MacOS resource forks in archives.
- Don't redirect to issue view on first search in Folder View

## v1.7.0 - SQLite Search

### ✨ Added

- Search
- Use SQLite Full Text Search v5 for search engine.
- Search syntax has changed. See the help popup at the end of the search bar.
- Use faster db column lookups for some search bar queries. Thanks @bmfrosty.
- You may remove the directory `config/whoosh_index`.
- Integrity Checks
- Faster more comprehensive db integrity checks run every night instead of at
  startup.
- Integrity checks can run on startup with environment variables documented in
  README.

### 🐛 Fixed

- Actually fix browser opening reader at correct bookmark.
- Also fixes progress calculation on browser cards.
- Fixed crashes when the upstream codex version is not accessible.
- Fixed possible race conditions with nightly maintenance.

## v1.6.19

### 🐛 Fixed

- Fix browser opening reader at correct bookmark.
- Fix for browser triple tap bug for android tablet browsers in desktop mode.
- Fix populating arcs in reading order menu in reader.
- Fix submitting old arc to reader API.
- Fix Version API blocking. Add check version admin task.
- Fix Library "Poll Every" validation.
- Fix Metadata dialog not scrolling sometimes.
- Fix file extension for downloaded PDF pages.

## v1.6.18 - Yanked, broken reader

## v1.6.17

### ✨ Added

- Admin Action buttons now responsive to view size.

### 🐛 Fixed

- Auto update wasn't comparing versions well.
- Possible fix for initializing admin flags crash.

## v1.6.16

### 🐛 Fixed

- Import may have been marking mounted drive's comics modified inappropriately.
- Import crash when moving comics.
- Relink deep orphan folders in the db instead of recreating them.
- Do not adopt orphan folders deleted from the filesystem.
- Admin Tab change password for user broke.
- More robust ui cache busting on library update.
- Fix minor error on metadata text boxes with null values.

## v1.6.15

### 🐛 Fixed

- Fix more Metadata links to browser groups not computing and resolving
  properly.

## v1.6.14

### 🐛 Fixed

- Fix Metadata links to browser groups not resetting topGroup properly.

## v1.6.13

### 🐛 Fixed

- Admin Panel Link was showing in the admin panel, not in the browser or reader.

## v1.6.12

### ✨ Added

- Native Windows installation instructions in the README thanks to
  @professionaltart.
- Anonymously send stats to improve Codex. See admin/flags for description and
  opt-out.

### 🐛 Fixed

- Detect iOS devices in Desktop Mode for proper iOS tap behavior.

## v1.6.9, v1.6.10, v1.6.11 - Yanked, bad network behavior and broken javascript

## v1.6.8

### 🐛 Fixed

- Fix OPDS streaming in lazy metadata mode for Chunky-like readers which require
  a page count.

## v1.6.7

### 🐛 Fixed

- OPDS authorization for some readers
- Remove superfluous debug exception trace on timezone endpoint.

## v1.6.6

### 🐛 Fixed

- User creation in admin panel broke.
- There was confusing UI on admin panel unauthorized screen.

## v1.6.5

### 🐛 Fixed

- Fix logout button not working.

## v1.6.4

### 🔥 Removed

- LOGLEVEL=VERBOSE deprecated for a long time. Use LOGLEVEL=DEBUG

### 🐛 Fixed

- Reader crash loading reader order arcs.
- OPDS datetimes now uniformly served in iso format.
- Fix browser filter menus clearing and loading irregularities.
- Fix parsing negative issue numbers in filenames.
- Log common non-ComicBookInfo archive comments with less alarm.

## v1.6.3

### ✨ Added

- Reader inherits the last browser view, with filters, as it's default reading
  arc.
- When browser page is less than 1, redirect to parent. When 1 and empty, show
  empty page.

### 🐛 Fixed

- The cover api was not accepting http basic (opds) authentication.

## v1.6.2

### 🐛 Fixed

- Fix pagination with more than 100 comics in the browser.

## v1.6.1

### ✨ Added

- Add a retry button on book load error and page load error pages.

### 🐛 Fixed

- Fix unable to login if anonymous users prohibited.
- Fix filter crash.
- Metadata was showing incorrect groups for individual comics

## v1.6.0 - Custom Covers & Breadcrumbs

### ✨ Added

- Custom Covers for Folders, Publishers, Imprints, Series and Story Arcs.
- Browser setting to choose Dynamic or First group covers. Thanks @Thakk.
- Breadcrumbs in the browser
- Reader can read by Volumes as well as by Series, Folder and StoryArc.
- More compact UI controls.
- Metadata tags can click to browse filtered on that tag.
- Experimental API throttling support. Search the README for "throttle".
- Add websocket updates for anonymous sessions
- Speed and caching optimizations.

### 🐛 Fixed

- OPDS http basic authorization fixed.
- Groups with the same name in different cases collapse into one group in the
  browser.
- Order By respects browser show groups settings.
- Fixed re-import of urls and identifiers.
- Fixed cleanup of some foreign keys when no longer used.
- Clean up all orphan folders on startup instead of first pass
- Fix creating bookmarks.
- Update browser sessions for user when users finish a book.

## v1.5.19

### 🐛 Fixed

- Metadata crash on folders.

## v1.5.18

### 🐛 Fixed

- Ignore comic pages from dotfiles and macOS resource forks.

## v1.5.17

### 🐛 Fixed

- Fix background color of browser card controls since vuetify update.

## v1.5.16

### 🐛 Fixed

- Fix creating and updating exclude groups.
- More Web & url tags parsed from metadata.

## v1.5.15

### 🐛 Fixed

- OPDS streaming broken for some clients (Chunky) without metadata.
- OPDS redirects for empty pages or 404's were crashing.
- OPDS uses filename fallback for title if missing metadata.

## v1.5.14

### ✨ Added

- Relative folder path is now searchable if Folder View enabled.
- More granular caching hopefully for better performance.

### 🐛 Fixed

- OPDS redirects were crashing.
- Null search was crashing metadata for single comics
- Fix a breakage with fast file static file serving.
- Change browser order by to something sensible when search cleared.

## v1.5.13

### 🐛 Fixed

- Fix root folder for library sometimes not created on import.
- Fix redirect loop in browser when all members of a group deleted.
- Fix browser pagination buttons not advancing.
- Fix OPDS v2 crash
- Fix browser throbber not appearing when making query.

## v1.5.12

### 🐛 Fixed

- Fix Folder browser offset pagination bug for folder with books and no folders.

## v1.5.11

### 🐛 Fixed

- Fix erroneous Folder View page out of bounds redirect.

## v1.5.10

### 🐛 Fixed

- Folder view was not showing all the books on mixed folder & book pages.
- Shutdown and Restart admin tasks were not working.

## v1.5.9

### 🐛 Fixed

- Crash when reading comics in folder view introduced in v1.5.8

## v1.5.8

### ✨ Added

- Even Lazier import when Import Metadata Admin flag turned off.
- issue: field search now combines numeric and suffix parts.

### 🐛 Fixed

- No search results was returning every comic instead of no comics.
- issue: field searching returned no results.
- issue\_number, community\_rating, & critical rating no longer require two
  digits of precision.
- Excess books included in reader arc/folder/series.

## v1.5.7

### 🐛 Fixed

- Pagination crash with more than 100 folders.
- Experimental fix for Synology Docker CHOWN\_PYTHON\_SITE\_PACKAGES=1

## v1.5.6

### 🐛 Fixed

- Fix sqlite limit crash when importing > \~1000 web urls.

## v1.5.5

### 🐛 Fixed

- Attempt to fix import crash processing too much metadata at once. Allow
  undocumented env variable to manipulate this: CODEX\_FILTER\_BATCH\_SIZE
  (default: 900)
- Fix search engine update crash for large collections.

## v1.5.4

### 🐛 Fixed

- Django 5 broke root\_path prefixing from the asgi server. Work around it.

## v1.5.3

### 🐛 Fixed

- Mouse horizontal scroll broken on Firefox.

## v1.5.2

### 🐛 Fixed

- OPDS titles were showing as "Unknown" for comics with tagged volumes.
- OPDS v2 was crashing.
- Cover displayed for group browser with Name ordering was inconsistent.
- Enable mouse drag horizontal scrolling in reader zoom mode.

## v1.5.1

### 🐛 Fixed

- OPDS v1 was not rendering any data.

## v1.5.0 - New Metadata Tags

### 💥 Breaking Changes

- The main database path has changed from `db.sqlite3` to `codex.sqlite3`
- This version forces a rebuild of the search index (not the main database)

### ✨ Added

- Admin Exclude groups compliment the existing Include groups.
- New metadata tags: Monochrome, Tagger, GTIN, Review, Identifiers, & Reading
  Direction. Available when comics are re-imported (Force Update recommended).
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

### 🐛 Fixed

- Some integrity checks weren't running on startup.
- The metadata page would sometimes crash for Admins.
- Moving a comic to a subfolder would crash.
- Moving a deep subfolders would crash.
- Moving a comic to the root folder would send the comic to the phantom zone.
- Updating comics would sometimes not delete removed tags.
- Series & Volumes no longer updated too often on import.
- Admin Actions was polling all libraries when one selected.
- OPDS was showing repeated titles.
- Vertical scroller tracking and updating improved.
- Page filenames are now sorted case insensitively which should improve order.

### 🧑‍💻 Developer

- Using comicbox v1 for metadata import.

## v1.4.3

### 🐛 Fixed

- Crash on undecodable characters in metadata.
- Search terms weren't applying to filter choices population.
- Fix name ordering. Show series & volume in browser cards if it affects name
  ordering.
- Shrink reader page change boxes to let toolbar activate on corner clicks.

### 🧑‍💻 Developer

- Big lint update.

## v1.4.2

### 🐛 Fixed

- Groups were not aggregating children properly when searched.
- Search could break Folder View.
- Changing the browser 'Order By' would sometimes not apply.
- Attempt to fix stale books appearing on reader load.

## v1.4.1

### 🐛 Fixed

- A bug that prevented folder view from displaying under some circumstances.

## v1.4.0 - Story Arcs

### ✨ Added

- Story Arc Top Group in Web & OPDS Browsers
- Support multiple Story Arcs per comic.
- Supports Mylar CSV StoryArc / StoryArcNumber extension to ComicInfo.xml
- Show only filter options that affect the current browse level.
- Reader has a Series/Folder/Story Arc order selector.
- Reader shows filename instead of metadata title if you've been browsing in
  File View
- Downloads now use the original filename from disk.

### 🐛 Fixed

- Folder was view displayed but crashed in OPDS even if disabled by admin.

## v1.3.14

### ✨ Added

- Better metadata extraction for PDFs.
- Support for ComicInfo StoryArcNumber, Review and GTIN tags.
- Order by Story Arc Number
- Do not detect .cbr files if unrar is not on the path.
- Display filename for comics in browser file view.

### 🔥 Removed

- Remove support for unrar.cffi

### 🐛 Fixed

- Import of ComicInfo Tags metadata.
- Never removed old missing metadata when updated.
- Error on moving folders.
- Fix saving last route between sessions.
- Better error messages if unrar is not on the path.

## v1.3.13

### 🐛 Fixed

- Group cover sometimes showing wrong cover for order.
- Rare import crash.

## v1.3.12

### ✨ Added

- OPDS 2 Last Read link.

### 🐛 Fixed

- Books without bookmarks could break parts of the reader.
- Remove clipboard UI hints when clipboard isn't available.

## v1.3.11

### ✨ Added

- Last Read Order By option for web and OPDS.
- Some Order By options now have a default descending order.
- OPDS 1 special top links limited to 100 entries.

### 🐛 Fixed

- OPDS 1 links did not include filters or order information.
- OPDS 1 page streaming broke.

## v1.3.10

### 🐛 Fixed

- Crash when reading from folder view.

## v1.3.9

### ✨ Added

- Experimental OPDS 2.0 Support.
- Create all comic covers admin task.
- Faster Metadata pages for web and OPDS.

### 🐛 Fixed

- Two pages mode broken.
- Credits not imported bug.
- Failed imports not removed when file removed bug.

## v1.3.8

### 🐛 Fixed

- Fix Basic Authentication not enabled for OPDS Cover, Page, and Download views.
- Tune low memory algorithm slightly lower for memory constrained systems.

### 🧑‍💻 Developer

- Use makefile and moved most scripts into bin.

## v1.3.7

### ✨ Added

- Metadata page links to groups to browse to.

### 🐛 Fixed

- Crash when moving comics.
- Container memory limits weren't detected for Linux kernels before 4.5
- Validation error detecting child and parent library paths incorrectly.
- Reader
    - Horizontal Reader was slow for comics with high page counts.
    - Vertical scroller was not tracking pages in fitTo Width or Orig modes.

### 🧑‍💻 Developer

- Django 4.2

## v1.3.6

### 🐛 Fixed

- Much lower memory tuning. Environment variables control tuning.
- Possible fix for vertical scroller page tracking for tall images.

## v1.3.5

### 🐛 Fixed

- OPDS sorting and filtering broke.
- Fixed Download URLs for clients that ignore headers like Chunky.
- Update Search Index now checks for more missing entries.

## v1.3.4

### 🐛 Fixed

- Number out of range errors for issue when search indexing.
- Total child pages of folders and groups sometimes overcounted, displaying half
  unread folders.
- Reader
    - Vertical Scroll
    - Remove black bottom margin from images.
    - Was loading every page in a comic at once.
    - Page tracking did not work with images larger than viewport width.

## v1.3.3

### 🐛 Fixed

- Number out of range errors when search indexing.
- Possible Search Index Remove Stale and Abort jobs not scheduled properly.
- OPDS missing entry ids rejected by Panels reader.
- Downloads had an extra period in the suffix.

## v1.3.2

### 🐛 Fixed

- Reader Fit To settings broken
- Possible files marked modified too often.

## v1.3.1

### 🐛 Fixed

- An import crash in create foreign keys.
- Admin table dates were always in UTC so sometime off by a day.

## v1.3.0 - Memory Management

### ✨ Added

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

### 🐛 Fixed

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

### ✨ Added

- Vertical scroll option for reader.
- Faster search index removes.
- Admin Users tab shows last user activity date.
- OPDSE PSE 1.2 extension for Panels `pse:lastReadDate`

### 🐛 Fixed

- Fixed next and previous book keyboard shortcuts.
- Improved OPDS acquisition page performance by removing more "categories"
  metadata.

## v1.2.8

### ✨ Added

- Search Index
- Improved search indexing times.
- Admin Flag to adjust nightly full optimization.
- OPDS "Newest Issues" Link replaced by "Recently Added" after user feedback.

### 🐛 Fixed

- Volume tags were often not scanned. Recommend using Force Reimport on all
  libraries.
- OPDS
    - Fix navigation links not inheriting view settings of current page.
    - Removed populating categories in OPDS to experiment with performance
      issues.
    - Fix OPDS pse lastRead tag.
    - Block library polling during database updates, fixes reindexing.

## v1.2.7

### 🐛 Fixed

- Trap final search index commit errors and try again without merging segments.
- Fix moving folders assigned no parent folder, displaying them in root.

## v1.2.6

### 🐛 Fixed

- Impose memory limits on search index writers.
- Impose items before write limits search index writer.
- Sort comics by path for the reader navigation when in Folder View.
- Remove inappropriate vertical scroll bars from page images.

## v1.2.5

### ✨ Added

- In Folder View the reader navigates by folder instead of series.

### 🐛 Fixed

- OPDS crash on missing 24 hour time setting input required.

## v1.2.4

### ✨ Added

- User configurable 24 hour time format.
- Reader
    - Displays covers as one page even in two page mode.
    - Read in Reverse mode.
    - Keymaps for adjusting page by one page in two page mode.
    - Previous and Next book navigation buttons and keymaps.

### 🐛 Fixed

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

### 🐛 Fixed

- Prevent search indexing starting over if it encounters errors.
- Fix download buttons.
- Fix admin settings drawer obscuring small screens.
- Fix scroll bars showing inapproporately on admin tables.
- Fix OPDS authors having 'i' appended.

## v1.2.2

### 🐛 Fixed

- Fix all items removed from search index after update.
- Speedups to cleaning up search engine ghosts.

## v1.2.1

### 🐛 Fixed

- Crash on building a fresh database.
- Fixed an importer crash when it tried to wait for changing files.
- Disabling Library Poll prevented manual polling.
- More explicit Poll Every hints in edit dialog.
- Repository link didn't open a new window.

## v1.2.0 - Faster PDFs & Fixed Multiprocessing

### ✨ Added

- Faster and more robust PDF support. Codex no longer depends on the poppler
  library.
- LOGLEVEL=VERBOSE deprecated in favor of DEBUG
- Stats page API accessible via API key as well as admin login.

### 🐛 Fixed

- Some Librarian Status messages would appear never to finish.

### 🧑‍💻 Developer

- The multiprocessing method is now S P A W N 💀 on all platforms.
- Websockets are now handled by customized Django channels
- aioprocessing Queue communicates between librarian and channels.

## v1.1.6

### 🐛 Fixed

- Fix rare deletion and recreation of all comics when inodes changed.

## v1.1.5

### ✨ Added

- Admin Stats tab
- Libraries can have a poll delay longer than 1 day.

### 🐛 Fixed

- Crash when removing comics.
- Admin Create & Update dialogs would get stuck open on submit.
- Delete expired and corrupt sessions every night.
- More liberal touch detection for more devices.

## v1.1.4

### 🐛 Fixed

- Multiprocessing speedup for large search engine indexing jobs
- Writes search engine data in segments.
- Search engine segment combiner optimizer runs nightly (and manually).

## v1.1.3

### 🐛 Fixed

- Fix some OPDS browsers unable to read comics.

## v1.1.2

### 🐛 Fixed

- Fix unable to initialize database on first run

## v1.1.0 - Whoosh

### ✨ Added

- Switch to Whoosh Search Engine.
- You may delete `config/xapian_index`.
- May run on Windows now?
- Moved db backups to `config/backups`.
- Backup database before migrations.

### 🔥 Removed

- Do not store search history for combobox across sessions.

### 🐛 Fixed

- Fix Admin Library folder picker.
- Uatu does a better job of ignoring device changes.
- Don't pop out of folder mode on searches.
- Fix showing error on unable to load comic image.

## v1.0.3

### ✨ Added

- Force update all failed imports admin task.

### 🐛 Fixed

- Fix moving folders to subfolder orphans folders bug.
- Fix id does not exist redirect loop.

## v1.0.2

### ✨ Added

- Support for Deflate64 zip compression algorithm.

### 🐛 Fixed

- Fix Failed Imports not retrying import when updated.
- Make db updates more durable and possibly problem comics paths in log.
- Discard orphan websocket connections from the connection pool.
- Fix Admin Status drawer closing at wrong time.

## v1.0.1

### ✨ Added

- Justify order-by field in browser cards.

### 🐛 Fixed

- Fixed next book change drawer opening settings drawer.
- Fixed zero padding on browser card issue numbers.

## v1.0.0 - Vue 3

### ✨ Added

- Removed old django admin pages.
- Shutdown task for admins.
- Configure logging with environment variables. See README.

### 🐛 Fixed

- Fix displaying error in login dialog.
- Fix saving community & critical rating filters to session
- Fix fit to screen not enlarging pages smaller than screen.

### 🧑‍💻 Developer

- Frontend is now Vuetify 3 over Vue 3. Using options API.

## v0.14.5

### 🐛 Fixed

- Fix crash on decoding some comics metadata charset encoding.

## v0.14.4

### 🐛 Fixed

- Fix login not available when AdminFlag Enable Non Users was unset.
- Fix server PicklingError logging bug.

## v0.14.3

### 🐛 Fixed

- Fix root\_path configuration

## v0.14.2

### 🐛 Fixed

- Fix Librarian process hanging due to logging deadlock.
- Fix reader keyboard shortcut help.
- Fix book change drawer appearing in the middle of books.

## v0.14.1

### 🐛 Fixed

- Resolve ties in browser ordering with default comic ordering.
- Always close book change drawer before reader opens.

## v0.14.0 - Sliding Pages

### ✨ Added

- Animated sliding pages on reader.
- Comic & PDF pages display loading, rendering and password errors.

### 🐛 Fixed

- Filters with compound names were not loading choices.
- Show only usable filters for current view as filter choices.
- Allow filtering by None values when None values exist.
- Handle an iOS bug with downloading pages and comics inside a PWA.
- Fixed PDF failure to render on load and after changing settings.
- Login & Change Password dialogs no longer activate Reader shortcuts by
  accident.

## v0.13.0 - Admin Panel

### ✨ Added

- Single Page Admin Panel.
- Users may now change their own passwords.
- OPDS
- Use facets for known User Agents that support them. Default to using entry
  links.
- Gain a Newest Issues facet, a Start top link and a Featured / Oldest Unread
  link.
- More metadata tags.
- Special thanks to @beville for UX research and suggestions
- HTTP Basic auth only used for OPDS.
- Frontend components do lazy loading, should see some speedups.

### 🐛 Fixed

- Fixed imprints & volume levels not displaying sometimes.
- Fix large images & downloads for some OPDS clients.

### 🧑‍💻 Developer

- API v3 is more restful.
- /api/v3/ displays API documentation.
- Vite replaces Vue CLI.
- Pina replaces Vuex.
- Vitest replaces Jest.
- Django livereload server and debug toolbar removed.

## v0.12.2

### 🐛 Fixed

- Fix OPDS downloading & streaming for Chunky Comic Reader.
- Hack in facets as nav links for Panels & Chunky OPDS readers.

## v0.12.1

### 🐛 Fixed

- Disable article ignore on name sort in folder view.
- Fix browser navigation bug with issues top group.

## v0.12.0 - Syndication

### ✨ Added

- OPDS v1, OPDS Streaming & OPDS Search support.
- Codex now accepts HTTP Basic authentication.
- If you run Codex behind a proxy that accepts HTTP Basic credentials that are
  different than those for Codex, be sure to disable authorization forwarding.
- Larger browser covers.
- Sort by name ignores leading articles in 11 languages.

### 🐛 Fixed

- Use defusexml to load xml metadata for safety.
- Removed process naming. My implementation was prone to instability.

## v0.11.0 - Task Monitor

### ✨ Added

- Librarian tasks in progress appear in the settings side drawer for
  adminstratiors.
- Covers are now created on demand by the browser, rather than on import.
- Browser Read filter.

### 🐛 Fixed

- Bookmark progress bar updates in browser after closing book.
- Metadata web links fix.

## v0.10.10

### ✨ Added

- Reader nav toolbar shows position in series.

### 🐛 Fixed

- Fix inability to log in when Enable Non Users admin flag is unset.
- Simplify Admin Library delete confirmation page to prevent OOM crash.
- Move controls away from iphone notch and home bar.

## v0.10.9

### ✨ Added

- Progressive Web App support
- Reader "Shrink to" settings replaced by "Fit to"

### 🐛 Fixed

- Fix null bookmark and count fields in metadata
- Fix indeterminate finished state when children have bookmark progress.
- Fix maintenance running inappropriately on first run. Crashed xapian database.
- Fix reader metadata keymap
- Thanks to ToxicFrog, who's been finding most of these bugs I'm fixing for a
  while.

## v0.10.8

### ✨ Added

- Accessibility enhancements for screen readers.

### 🐛 Fixed

- Fixed reader nav clicks always showing the toolbars.
- Attempt to fix unwanted browser toolbars when treated as mobile app
- Wait half a second before displaying reader placeholder spinner.
- Fix metadata missing search query.
- Fix metadata cache busting.

## v0.10.7

### ✨ Added

- Browser tries to scroll to closed book to keep your place.

### 🐛 Fixed

- Fixed missing lower click area on browser cards.
- Fixed session bookmark interfering with logged in user bookmark.

## v0.10.6 - Broken docker container

## v0.10.5

### ✨ Added

- Reader shrink to screen setting becomes fit to screen and embiggens small
  images.
- Reader changing to the next book now has visual feedback and requires two
  clicks.

### 🐛 Fixed

- Removed vertical scrollbars when Reader shrunk to height.
- Don't disturb the view when top group changes from higher to lower.

## v0.10.4

### ✨ Added

- Shrink to Screen reader setting.
- Reader throbber if a page takes longer than a quarter second to load.

### 🐛 Fixed

- Fix double tap for non-iOS touch devices.

## v0.10.3

### 🐛 Fixed

- Fix PDF going blank when settings change.
- Remove vestigial browser scrollbars when they're not needed. Thanks to
  ToxicFrog.
- Fix cover cleanup maintenance task.

## v0.10.2

### 🐛 Fixed

- URLS dictate view over top group. Fixes linking into views.
- Fix possible cover generation memory leak.
- Build a deadfall trap for search indexer zombies. Use Offspring's brains as
  bait.

## v0.10.1

### 🐛 Fixed

- Linked old top level comics orphaned by library folders migration.

## v0.10.0 - Portable Document Format

### ✨ Added

- PDF support. Optional poppler-utils binary package needed to generate PDF
  cover thumbnails.
- CBT support. Tarball comic archives.
- Alphanumeric issue support. Requires rescanning existing comics.
- Individual top level folders for each library.
- Don't duplicate folder name in filename sort.

### 🐛 Fixed

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

### ✨ Added

- Filename order by option. Disabled if the "Enable Folder View" Admin Flag is
  off.

### 🐛 Fixed

- Fix comicbox config crash.
- Use codex config namespace (\~/.config/codex) so codex doesn't interfere with
  standalone comicbox configs.
- Comic issue numbers display to two decimal points instead of using ½ glyphs.

## v0.9.13

### 🐛 Fixed

- Fix root\_path configuration for running codex in url sub-paths
- Parse new filename patterns for metadata.
- Slightly faster comic cover generation.

## v0.9.12

### ✨ Added

- Disable reader prev/next touch swiping for phone sized browsers.

### 🐛 Fixed

- Fix setting global reader settings.
- Fixed reader settings not applying due to caching.
- Bust reader caches when library updates.
- Reader titles smaller and wrap on mobile.
- Fixed deep linking into reader.

## v0.9.11

### ✨ Added

- Codex processes show names in ps and thread names on Linux.
- Add Poll libraries action to FailedImports Admin Panel.
- Space and shift-space previous and next reader shortcuts.
- Reader settings UI redesigned to be clearer.

### 🐛 Fixed

- Fixed covers not creating on import.
- Covers update in browser when updated on disk.
- Create missing covers on startup.
- Bust browser cache when library updates.
- Reader settings were not applying in some cases.
- Fixed crash updating latest codex software version from the internet.
- Fixed crash loading admin page.

## v0.9.10 - Yanked, crash loading admin page

## v0.9.9

### ✨ Added

- Update search index daily.
- Clean up orphan comic covers every night.

### 🐛 Fixed

- Fixed combining CBI credits with other format credits
- Failed imports notification appears only for new failed imports.

## v0.9.8

### ✨ Added

- More comprehensive metadata sanitizing before import.
- Reduced time checking to see if files have finished writing before import.
- Uniform format for metadata parsing logging.
- Credits sorted by last name.

### 🐛 Fixed

- Fixed search index update crash while database is still updating.
- Fixed issues larger than 99 bug.
- Fixed issue not imported due to metadata cleaning bug.
- Fixed crash updating search index while library was still updating.
- Thread error trapping and diagnostics to root out zombie process issue.
- Sort numeric terms in filter menus numerically not alphabetically.
- Fixed comic name display wrapping in browser.

## v0.9.7

### ✨ Added

- Clean up unused foreign keys once a day instead of after every import.
- Clean up unused foreign keys librarian job available in admin panel.

### 🐛 Fixed

- Coerce decimal values into valid ranges and precision before importing.

## v0.9.6

### ✨ Added

- Replace description field with more common ComicInfo comments field.
- Log files now rotate by size instead of daily.
- Log path for failed imports and cover creation.

### 🐛 Fixed

- Don't open browser when a library changes when reading a comic.
- Fixed crash creating illegal dates on import.

## v0.9.5

### 🐛 Fixed

- Use an allow list for importing metadata to prevent crashes.

## v0.9.4

### 🐛 Fixed

- Fixed crash when importing comments metadata.

## v0.9.3

### 🐛 Fixed

- Import credits data for CBI and CIX tagged comics.
- More liberal metadata decimal parsing.

## v0.9.2

### 🐛 Fixed

- Fix rare migration bug for Cover Artist role.

## v0.9.1

### 🐛 Fixed

- Fix to library group integrity checker

## v0.9.0 - Private Libraries

### ✨ Added

- Libraries may have access restricted to certain user groups.
- The "Critical Rating" tag is now a decimal value.
- The "Community Rating" tag replaced "User Rating" tag, a decimal value.
- Cover Credits role replaced by "Cover Artist".
- Reader has a "Download Page" button.
- Metadata dialog highlights filtered items.
- Metadata dialog is faster.
- Admin Queue Job for creating missing comic covers.

## v0.8.0 - Search

### 💥 Breaking Changes

- Codex now requires the Xapian library to run as a native application

### ✨ Added

- Metadata search field in browser
- Settings dialogs replaced with side drawers
- Changed some keyboard shortcuts in reader.
- "group by" renamed to "top group".
- Admin panel gained a Queue Jobs page.

### ♻️ Changed

- Codex is GPLv3

### 🔥 Removed

- The linux/armhf platform is no longer published for Docker.

### 🐛 Fixed

- Browser does a better job of remembering your last browser view on first load.
- Reader's "close book" button now does a better job returning you to your last
  browser view.
- Metadata panel cleanup and fix some missing fields.

## v0.7.5

### 🐛 Fixed

- Fix integrity cleanup check for old comic\_folder relations that prevented
  migrations.

## v0.7.4

### 🐛 Fixed

- Fix integrity cleanup check for more types of integrity errors that may have
  prevented clean db migrations.
- Fix last filter, group, sort not loading properly for some new views.

## v0.7.3

### ✨ Added

- Database indexing speedups.

### 🐛 Fixed

- Fix crash updating latest version.
- Fix a folder not found crash in folder view.

## v0.7.2

### 🐛 Fixed

- Fix another integrity check bug

## v0.7.1

### ✨ Added

- Added `CODEX_SKIP_INTEGRITY_CHECK` env var.

### 🐛 Fixed

- Fix and integrity check crash that happened with an older databases.

## v0.7.0 - Feels Snappier

### 💥 Breaking Changes

- v0.7.0 changes the database schema. Databases run with v0.7.0+ will not run on
  previous versions of codex.

### ✨ Added

- Big speed up to importing comics for large imports.
- Speed up creating comic covers on large imports.
- Admin Panel options for polling (formerly "scanning") and watching events have
  changed names.
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

### 🐛 Fixed

- Fixed metadata screen displaying incorrect information.
- Now compatible with python 3.10.

## v0.6.8

### ✨ Added

- Browser now tells you what kind of items you're looking at.
- Reader swiping navigation
- Reader keyboard shortcut help dialog
- Tentative linux/armhf support. No way for me to test this
- Vacuum the sqlite database once a day to prevent bloat
- Corrupt database rebuild procedure. See README.

### 🐛 Fixed

- Fixes some import bugs with filename parsing when there are no tags
- Fixed two page view toggle hotkey

## v0.6.7

### ♻️ Changed

- Dark admin pages and fix template overrides.

## v0.6.6

### 🧑‍💻 Developer

- Automate multi-arch builds

## v0.6.5

### 🧑‍💻 Developer

- Build Docker images for amd64 & arm64 manually.

## v0.6.4

### 🐛 Fixed

- Fix reader bug that only displayed first page

## v0.6.3

### ✨ Added

- Add LOGLEVEL environment variable.
    - Set to DEBUG to see everything.
- Removed DEV environment variable.
- Possible fix for newly imported covers not displaying.

## v0.6.2

### 🐛 Fixed

- Fixed intermittent Librarian startup crash in docker.
- Fixed DEBUG environment variable to be able to run in production.

### 🧑‍💻 Developer

- Added DEV environment variable for dev environment.

## v0.6.1

### 🐛 Fixed

- Fix librarian startup crash. Prevented admin actions from happening.

## v0.6.0 - Better Filtering and Sorting

### ✨ Added

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

### 🐛 Fixed

- Fixed a bug importing Story Arc Series Groups and Genres. Requires re-import
  to correct.
- Fixed a bug with sorting that grouped improperly and showed the wrong covers
  for reverse sorts.
- Scanning notifications on login not disappearing bug squashed
- Fixed a bug where the browser settings menu wouldn't close when opening a
  dialog

## v0.5.18

### 🐛 Fixed

- Fix filters not changing display bug

## v0.5.17

### 🐛 Fixed

- Fix root\_path not parsing bug

## v0.5.16

### 🐛 Fixed

- Fix broken startup when parsing json shared between front and back end

## v0.5.15

### ✨ Added

- Metadata popup is now faster.
- Metadata popup now shows created\_at, updated\_at and path (if admin).
- Removed numeric and common password validators. Made the minimum length 4.

## v0.5.14

### ✨ Added

- Metadata view for browse containers. Also observes filters.
- Covers now regenerate on re-import.

### 🐛 Fixed

- Fix scanning notification
- Fix unable to delete libraries bug

## v0.5.13

### ✨ Added

- Admin Flag for automatically updating codex
- Force updates from the admin panel with an Admin Flag action
- Snackbar for notifying about failed imports

## v0.5.12

### ✨ Added

- Admin page for failed imports
- Snackbar tells admins when scans are happening
- Report the latest version available in the browser footer tooltip
- Admin flag for disabling codex for non-users

## v0.5.11

### ✨ Added

- Browser rows now adapt to browse tile size
- Browser covers for containers now match data we're sorting by
- Serve static files faster

### 🐛 Fixed

- Reader fix settings for all comics were not setting properly
- Fix bookmarks for sessions that aren't logged in

## v0.5.10

### 🐛 Fixed

- Fix filtering bugs
- Fix mark read/unread bugs
- Fix reader settings not setting properly
- Fix reader images positioning
- Fix minor crash closing books with uninitialized browser app

## v0.5.9

### ✨ Added

- Display sort key value in browse tile
- Display standard image for missing covers
- Slightly more helpful 404 page

### 🐛 Fixed

- Fix sorting for folder view
- Fix import bugs

## v0.5.8 - Version bump for the 0.5.7 upload mistake

## v0.5.7

### ✨ Added

- Allow credits with an empty role
- Pagination of large browse results
- Center comic pages better
- Add download link to browser menu
- Log to files as well as console

### 🐛 Fixed

- Fix import crashes
- Remove scan locks on startup

## v0.5.6

### 🐛 Fixed

- Websocket path security wasn't handling leading slashes well. Skip it.

## v0.5.5

### 🐛 Fixed

- Revert to whitenoise 5.1.0 which works with subpaths

## v0.5.4

### 🐛 Fixed

- Fix crash on start if all static dirs do not exist.

## v0.5.3

### ✨ Added

- Versioned API
- Toast popup for admins indicating libraries are scanning.
- Periodic frontend refresh during long scans.
- Codex version displayed in browser footer

### 🐛 Fixed

- Fixed login bug introduces in v0.5.3 (thanks hubcaps)
- Fixed filtering bug introduced in v0.5.2

## v0.5.2

### ✨ Added

- Lazy load filter choices when the menu opens
- Documentation moved into admin panel

### 🐛 Fixed

- Fix multiprocessing for Windows

## v0.5.1

### 🐛 Fixed

- Minor bugfixes.

## v0.5.0 - First useful working version

### ✨ Added

- Productionized alpha release

## v0.4.0 - Polished UI

### ✨ Added

- Polished VueJS frontend

## v0.3.0 - I'm a frontend developer!

### ✨ Added

- Single Page VueJS frontend PoC without much styling

## v0.2.0 - It's alive

### ✨ Added

- Working application with all initial features
- Django frontend

## v0.1.0 - Hello world

### ✨ Added

- Proof of concept.
