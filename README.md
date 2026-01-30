# Codex

A comic archive browser and reader.

<img src="codex/img/logo.svg" style="
height: 128px;
width: 128px;
border-radius: 128px;
" />

## ✨ Features

- Codex is a web server.
- Full text search of comic metadata and bookmarks.
- Filter and sort on all comic metadata and unread status per user.
- Browse a tree of Publishers, Imprints, Series, Volumes, or your own folder
  hierarchy, or by tagged Story Arc.
- Read comics in a variety of aspect ratios and directions that fit your screen.
- Watches the filesystem and automatically imports new or changed comics.
- Anonymous browsing and reading or reigistered users only, to your preference.
- Per user bookmarking & settings, even before you make an account.
- Private Libraries accessible only to certain groups of users.
- Reads CBZ, CBR, CBT, and PDF formatted comics.
- Syndication with OPDS 1 & 2, streaming, search and authentication.
- Add custom covers to Folders, Publishers, Imprints, Series, and Story Arcs.
- Remote-User HTTP header SSO support.
- Runs in 1GB of RAM, faster with more.
- GPLv3 Licenced.

### Examples

- _Filter by_ Story Arc and Unread, _Order by_ Publish Date to create an event
  reading list.
- _Filter by_ Unread and _Order by_ Added Time to see your latest unread comics.
- _Search by_ your favorite character to find their appearances across different
  comics.

## 👀 Demonstration

You may browse a [live demo server](https://demo.codex-reader.app/) to get a
feel for Codex.

## 📜 News

Codex has a [NEWS file](NEWS.md) to summarize changes that affect users.

## 🕸️ HTML Docs

[HTML formatted docs are available here](https://codex-comic-reader.readthedocs.io)

## 📦 Installation

### Install & Run with Docker

Run the official [Docker Image](https://hub.docker.com/r/ajslater/codex).
Instructions for running the docker image are on the Docker Hub README. This is
the recommended way to run Codex.

You'll then want to read the [Administration](#administration) section of this
document.

### Install & Run on HomeAssistant server

If you have a [HomeAssistant](https://www.home-assistant.io/) server, Codex can
be installed with the following steps :

- Add the `https://github.com/alexbelgium/hassio-addons` repository by
  [clicking here](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Falexbelgium%2Fhassio-addons)
- Install the addon :
  [click here to automatically open the addon store, then install the addon](https://my.home-assistant.io/redirect/supervisor)
- Customize addon options, then then start the add-on.

### Install & Run as a Native Application

You can also run Codex as a natively installed python application with pip.

#### Binary Dependencies

You'll need to install the appropriate system dependencies for your platform
before installing Codex.

##### Linux Dependencies

###### Debian Dependencies

...and Ubuntu, Mint, MX, Window Subsystem for Linux, and others.

```sh
apt install build-essential libimagequant0 libjpeg-turbo8 libopenjp2-7 libssl libyaml-0-2 libtiff6 libwebp7 python3-dev python3-pip sqlite3 unrar zlib1g
```

Versions of packages like libjpeg, libssl, libtiff may differ between flavors
and versions of your distribution. If the package versions listed in the example
above are not available, try searching for ones that are with `apt-cache` or
`aptitude`.

```sh
apt-cache search libjpeg-turbo
```

###### Alpine Dependencies

```sh
apk add bsd-compat-headers build-base jpeg-dev libffi-dev libwebp openssl-dev sqlite yaml-dev zlib-dev
```

##### Install unrar Runtime Dependency on non-debian Linux

Codex requires unrar to read CBR formatted comic archives. Unrar is often not
packaged for Linux, but here are some instructions:
[How to install unrar in Linux](https://www.unixtutorial.org/how-to-install-unrar-in-linux/)

Unrar as packaged for Alpine Linux v3.14 seems to work on Alpine v3.15+

##### macOS Dependencies

Using [Homebrew](https://brew.sh/):

```sh
brew install jpeg libffi libyaml libzip openssl python sqlite unrar webp
```

#### Installing Codex on Linux on ARM (AARCH64) with Python 3.13

Pymupdf has no pre-built wheels for AARCH64 so pip must build it and the build
fails on Python 3.13 without this environment variable set:

```sh
PYMUPDF_SETUP_PY_LIMITED_API=0 pip install codex
```

You will also have to have the `build-essential` and `python3-dev` or equivalent
packages installed on on your Linux.

#### Windows Installation

Windows users are encouraged to use Docker to run Codex, but it will also run
natively on the Windows Subsystem for Linux.

Installation instructions are in the
[Native Windows Dependencies Installation Document](WINDOWS.md).

#### Run Codex Natively

Once you have installed codex, the codex binary should be on your path. To start
codex, run:

```sh
codex
```

### Use Codex

Once installed and running you may navigate to <http://localhost:9810/>

## 👑 Administration

### Navigate to the Admin Panel

- Click the hamburger menu ☰ to open the browser settings drawer.
- Log in as the 'admin' user. The default administrator password is also
  'admin'.
- Navigate to the Admin Panel by clicking on its link in the browser settings
  drawer after you have logged in.

### Change the Admin password

The first thing you should do is log in as the admin user and change the admin
password.

- Navigate to the Admin Panel as described above.
- Select the Users tab.
- Change the admin user's password using the small lock button.
- You may also change the admin user's name with the edit button.
- You may create other users and grant them admin privileges by making them
  staff.

### Add Comic Libraries

The second thing you will want to do is log in as an Administrator and add one
or more comic libraries.

- Navigate to the Admin Panel as described above.
- Select the Libraries tab in the Admin Panel
- Add a Library with the "+ LIBRARY" button in the upper left.

### Reset the admin password

If you forget all your superuser passwords, you may restore the original default
admin account by running codex with the `CODEX_RESET_ADMIN` environment variable
set.

```sh
CODEX_RESET_ADMIN=1 codex
```

or, if using Docker:

```sh
docker run -e CODEX_RESET_ADMIN=1 -v host-parent-dir/config:/config ajslater/codex
```

### Private Libraries

In the Admin Panel you may configure private libraries that are only accessible
to specific groups.

A library with _no_ groups is accessible to every user including anonymous
users.

A library with _any_ groups is accessible only to users who are in those groups.

Use the Groups admin panel to create groups and the Users admin panel to add and
remove users to groups.

#### Include and Exclude Groups

Codex can make groups for libraries that exclude groups of users or exclude
everyone and include only certain groups of users.

### PDF Metadata

Codex reads PDF metadata from the filename, PDF metadata fields and also many
formats of common complex comic metadata if they are embedded in the PDF
`keywords` field.

If you decide to include PDFs in your comic library, I recommend taking time to
rename your files so Codex can find some metadata. Codex recognizes several file
naming schemes. This one has good results:

`{series} v{volume} #{issue} {title} ({year}) {ignored}.pdf`

Complex comic metadata, such as ComicInfo.xml, can be also be embedded in the
keywords field by using the [comicbox](https://github.com/ajslater/comicbox)
command line tool. Codex will read this data because it relies on comicbox
internally. Not many people use comicbox or embedded metadata in PDFs in this
fashion, so you likely won't find it unless you've added it yourself.

### 🗝️ API with Key Access

Codex has a limited number of API endpoints available with API Key Access. The
API Key is available on the admin/stats tab.

## 🎛️ Configuration

### Config Dir

The default config directory is `config/` directly under the working directory
you run codex from. You may specify an alternate config directory with the
environment variable `CODEX_CONFIG_DIR`.

The config directory contains a file named `hypercorn.toml` where you can
specify ports and bind addresses. If no `hypercorn.toml` is present Codex copies
a default one to that directory on startup.

The default values for the config options are:

```toml
bind = ["0.0.0.0:9810"]
quick_bind = ["0.0.0.0:9810"]
root_path = "/codex"
```

The config directory also holds the main sqlite database, the Whoosh search
index, a Django cache and comic book cover thumbnails.

### Environment Variables

#### General

- `TIMEZONE` or `TZ` will explicitly set the timezone in long format (e.g.
  `"America/Los Angeles"`). This is useful inside Docker because codex cannot
  automatically detect the host machine's timezone.
- `CODEX_AUTH_REMOTE_USER` will allow unauthenticated logins with the
  Remote-User HTTP header. This can be very insecure if not configured properly.
  Please read the Remote-User docs devoted to it below.
- `CODEX_CONFIG_DIR` will set the path to codex config directory. Defaults to
  `$CWD/config`
- `CODEX_RESET_ADMIN=1` will reset the admin user and its password to defaults
  when codex starts.
- `CODEX_FIX_FOREIGN_KEYS=1` will check for and try to repair illegal foreign
  keys on startup.
- `CODEX_INTEGRITY_CHECK=1` will perform database integrity check on startup.
- `CODEX_FTS_INTEGRITY_CHECK=1` will perform an integrity check on the full text
  search index.
- `CODEX_FTS_REBUILD=1` will rebuild the full text search index.
- `DEBUG_TRANSFORM` will show verbose information about how the comicbox library
  reads all archive metadata sources and transforms it into a the comicbox
  schema.

#### Logging

- `LOGLEVEL` will change how verbose codex's logging is. Valid values are
  `ERROR`, `WARNING`, `INFO`, `DEBUG`. The default is `INFO`.
- `CODEX_LOG_DIR` sets a custom directory for saving logfiles. Defaults to
  `$CODEX_CONFIG_DIR/logs`
- `CODEX_LOG_TO_FILE=0` will not log to files.
- `CODEX_LOG_TO_CONSOLE=0` will not log to the console.

#### Throttling

Codex contains some experimental throttling controls. The value supplied to
these variables will be interpreted as the maximum number of allowed requests
per minute. For example, the following settings would limit each described group
to 2 queries per second.

- `CODEX_THROTTLE_ANON=30` Anonymous users
- `CODEX_THROTTLE_USER=30` Authenticated users
- `CODEX_THROTTLE_OPDS=30` The OPDS v1 & v2 APIs (Panels uses this for search)
- `CODEX_THROTTLE_OPENSEARCH=30` The OPDS v1 Opensearch API

### Reverse Proxy

[nginx](https://nginx.org/) is often used as a TLS terminator and subpath proxy.

Here's an example nginx config with a subpath named '/codex'.

```nginx
# HTTP
proxy_set_header   Host $http_host;
proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header   X-Forwarded-Host $server_name;
proxy_set_header   X-Forwarded-Port $server_port;
proxy_set_header   X-Forwarded-Proto $scheme;
proxy_set_header   X-Real-IP $remote_addr;
proxy_set_header   X-Scheme $scheme;
# Websockets
proxy_http_version 1.1;
proxy_set_header   Upgrade $http_upgrade;

proxy_set_header Connection "Upgrade" location /codex {
    proxy_pass       http://codex:9810;
    # Codex reads http basic authentication.
    # If the nginx credentials are different than codex credentials use this line to
    #   not forward the authorization.
    proxy_set_header Authorization "";
}
```

Specify a reverse proxy sub path (if you have one) in `config/hypercorn.toml`

```toml
root_path = "/codex"
```

#### Nginx Reverse Proxy 502 when container refreshes

Nginx requires a special trick to refresh dns when linked Docker containers
recreate. See this
[nginx with dynamix upstreams](https://tenzer.dk/nginx-with-dynamic-upstreams/)
article.

#### Single Sign On and Third Party Authentication

##### OAuth & OIDC

Codex is not an OIDC client at this time. However the following Remote-User and
Token Authentication methods may assist other services in providing Single Sign
On.

##### Remote-User Authentication

Remote-User authentication tells Codex to accept a username from the webserver
and assume that authentication has already been done. This is very insecure if
you haven't configured an authenticating reverse proxy in front of Codex.

Here's a snipped for configuring nginx with tinyauth to provide this header.
This snipped it incomplete and assumes that the rest of nginx tinyauth config
has been done:

```nginx
auth_request_set $tinyauth_remote_user $upstream_http_remote_user;
proxy_set_header Remote-User $tiny_auth_user;
```

⚠️ Only turn on the `CODEX_AUTH_REMOTE_USER` environment variable if your
webserver sets the `Remote-User` header itself every time for the Codex
location, overriding any malicious client that might set it themselves. ⚠️

##### HTTP Token Authentication

You can also configure your proxy to add token authentication to the headers.
Codex will read “Bearer” prefixed authorization tokens. The token is unique for
each user and may be found in the Web UI sidebar. You must configure your proxy
or single sign on software to send this token.

```nginx
set              user_token 'user-token-taken-from-web-ui';
proxy_set_header Authorization "Bearer $user_token";
```

### Restricted Memory Environments

Codex can run with as little as 1GB available RAM. Large batch jobs –like
importing and indexing tens of thousands of comics at once– will run faster the
more memory is available to Codex. The biggest gains in speed happen when you
increase memory up to about 6GB. Codex batch jobs do get faster the more memory
it has above 6GB, but with diminishing returns.

If you must run Codex in an admin restricted memory environment you might want
to temporarily give Codex a lot of memory to run a very large import job and
then restrict it for normal operation.

## 📖 Use

### 👤 Sessions & Accounts

Once your administrator has added some comic libraries, you may browse and read
comics. Codex will remember your preferences, bookmarks and progress in the
browser session. Codex destroys anonymous sessions and bookmarks after 60 days.
To preserve these settings across browsers and after sessions expire, you may
register an account with a username and password. You will have to contact your
administrator to reset your password if you forget it.

### ᯤ OPDS

Codex supports OPDS syndication and OPDS streaming. You may find the OPDS url in
the side drawer. It should take the form:

`http(s)://host.tld(:9810)(/root_path)/opds/v1.2/`

or

`http(s)://host.tld(:9810)(/root_path)/opds/v2.0/`

#### OPDS v1 Clients

- iOS
    - [Panels](https://panels.app/)
    - [PocketBooks](https://pocketbook.ch/)
    - [KYBook 3](http://kybook-reader.com/)
    - [Chunky Comic Reader](https://apps.apple.com/us/app/chunky-comic-reader/id663567628)
- Android
    - [Moon+](https://play.google.com/store/apps/details?id=com.flyersoft.moonreader)
    - [Librera](https://play.google.com/store/apps/details?id=com.foobnix.pdf.reader)

Kybook 3 does not seem to support http basic authentication, so Codex users are
not supported.

#### OPDS v2 Clients

OPDS 2.0 is a newer protocol that is only just starting to be supported by new
clients.

- [Stump (Alpha Test)](https://www.stumpapp.dev/guides/mobile/app)
- [Readest](https://readest.com/) (No page streaming yet, download only)

#### OPDS Authentication

##### OPDS Login

The few clients that implement the OPDS 1.0 Authentication spec present the user
with a login screen for interactive authentication.

##### HTTP Basic

Some OPDS clients allow configuring HTTP Basic authentication in their OPDS
server settings. If the don't, you will have to add your username and password
to the URL. In that case the OPDS url will look like:

`http(s)://username:password@codex-server.tld(:9810)(/root_path)/opds/v1.2/`

##### HTTP Token

Some clients allow adding a unique login token to the HTTP headers. Codex will
read "Bearer" prefixed authorization tokens. The token is unique for each user
and may be found in the Web UI sidebar.

#### Supported OPDS Specifications

##### OPDS v1

- [OPDS 1.2](https://specs.opds.io/opds-1.2.html)
- [OPDS-PSE 1.2](https://github.com/anansi-project/opds-pse/blob/master/v1.2.md)
- [OPDS Authentication 1.0](https://drafts.opds.io/authentication-for-opds-1.0.html)

##### OPDS v2

- [OPDS 2.0 (draft)](https://drafts.opds.io/opds-2.0.html)
- [OPDS 2.0 Digital Visual Narratives Profile (DiViNa)](https://github.com/readium/webpub-manifest/blob/master/profiles/divina.md)
- [OPDS 2.0 Authentication (proposal)](https://github.com/opds-community/drafts/discussions/43)
- [OPDS 2.0 Progression (proposal)](https://github.com/opds-community/drafts/discussions/67)

##### OpenSearch v1

- [OpenSearch 1.1 (draft)](https://github.com/dewitt/opensearch)

## [🩺 Troubleshooting](#troubleshooting)

### 📒 Logs

Codex collects its logs in the `config/logs` directory. Take a look to see what
th e server is doing.

You can change how much codex logs by setting the `LOGLEVEL` environment
variable. By default this level is `INFO`. To see more verbose messages, run
codex like:

```sh
LOGLEVEL=DEBUG codex
```

### Watching Filesystem Events with Docker

Codex tries to watch for filesystem events to instantly update your comic
libraries when they change on disk. But these native filesystem events are not
translated between macOS & Windows Docker hosts and the Docker Linux container.
If you find that your installation is not updating to filesystem changes
instantly, you might try enabling polling for the affected libraries and
decreasing the `poll_every` value in the Admin console to a frequency that suits
you.

### Emergency Database Repair

If the database becomes corrupt, Codex includes a facility to rebuild the
database. Place a file named `rebuild_db` in your Codex config directory like
so:

```sh
touch config/rebuild_db
```

Shut down and restart Codex.

The next time Codex starts it will back up the existing database and try to
rebuild it. The database lives in the config directory as the file
`config/db.sqlite3`. If this procedure goes kablooey, you may recover the
original database at `config/backups/codex.sqlite3.before-rebuild`. Codex will
remove the `rebuild_db` file.

### Warnings to Ignore

#### StreamingHttpResponse Iterator Warning

```pycon
packages/django/http/response.py:517: Warning: StreamingHttpResponse must consume synchronous iterators in order to serve them asynchronously. Use an asynchronous iterator instead.
```

This is a known warning and does not represent anything bad happening. It's an
artifact of the Django framework slowly supporting asynchronous server endpoints
and unfortunately isn't practical to remove yet.

## 📚Alternatives to Codex

- [Kavita](https://www.kavitareader.com/) has light metadata filtering/editing,
  supports comics, eBooks, and features for manga.
- [Komga](https://komga.org/) has light metadata editing and duplicate page
  elimination.
- [Ubooquity](https://vaemendis.net/ubooquity/) reads both comics and eBooks.

## 🔧 Popular comic utilities

- [Mylar](https://github.com/mylar3/mylar3) is the best comic book manager which
  also has a built in reader.
- [Comictagger](https://github.com/comictagger/comictagger) is a comic metadata
  editor. It comes with a command line and desktop GUI. It will tag identified
  comics from online database sources.
- [Metron Tagger](https://github.com/Metron-Project/metron-tagger) is a command
  line comic metadata editor. It will tag identified comics from online database
  sources.
- [Comicbox](https://github.com/ajslater/comicbox) is a powerful command line
  comic metadata editor and multi metadata format synthesizer. It is what Codex
  uses under the hood to read comic metadata.

## 🤝 Contributing

### 🐛 Bug Reports

Issues and feature requests are best filed on the
[Github issue tracker](https://github.com/ajslater/codex/issues).

### 🛠 Develop

Codex's git repo is mirrored on [Github](https://github.com/ajslater/codex/)

Codex is a Django Python webserver with a VueJS front end.

`/codex/codex/` is the main django app which provides the webserver and
database.

`/codex/frontend/` is where the vuejs frontend lives.

Most of Codex development is now controlled through the Makefile. Type `make`
for a list of commands.

## 💬 Support

By the generosity of the good people of
[Mylar](https://github.com/mylar3/mylar3), I and other Codex users answer
questions on the [Mylar Discord](https://discord.gg/6UG94R7E8T). Please use the
`#codex-support` channel to ask for help with Codex.

## 🔗 Links

- [Docker Image](https://hub.docker.com/r/ajslater/codex)
- [PyPi Package](https://pypi.org/project/codex/)
- [GitHub Project](https://github.com/ajslater/codex/)

## 🙏🏻 Thanks

- Thanks to [Aurélien Mazurie](https://pypi.org/user/ajmazurie/) for allowing me
  to use the PyPi name 'codex'.
- To [ProfessionalTart](https://github.com/professionaltart) for providing
  native Windows installation instructions.
- Thanks to the good people of
  [#mylar](https://github.com/mylar3/mylar3#live-support--conversation) for
  continuous feedback and comic ecosystem education.

## 😊 Enjoy

![These simple people have managed to tap into the spiritual forces that mystics and yogis spend literal lifetimes seeking. I feel... ...I feel...](strange.jpg)
