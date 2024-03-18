Codex

A comic archive browser and reader.

<img src="codex/static_src/img/logo.svg" style="
height: 128px;
width: 128px;
border-radius: 128px;
" />

## <a name="features">✨ Features</a>

- Codex is a web server.
- Full text search of metadata and bookmarks.
- Filter and sort on all comic metadata and unread status per user.
- Browse a tree of publishers, imprints, series, volumes, or your own folder
  hierarchy.
- Read comics in a variety of aspect ratios and directions that fit your screen.
- Per user bookmarking. Per browser bookmarks even before you make an account.
- Watches the filesystem and automatically imports new or changed comics.
- Private Libraries accessible only to certain groups of users.
- Reads CBZ, CBR, CBT, and PDF formatted comics.
- Syndication with OPDS 1 & 2, streaming, search and authentication.
- Runs in 1GB of RAM, faster with more.

### Examples

- _Filter by_ Story Arc and Unread, _Order by_ Publish Date to create an event
  reading list.
- _Filter by_ Unread and _Order by_ Added Time to see your latest unread comics.
- _Search by_ your favorite character to find their appearances across different
  comics.

## <a name="demonstration">👀 Demonstration</a>

You may browse a [live demo server](https://codex.sl8r.net/) to get a feel for
Codex.

## <a name="news">📜 News</a>

Codex has a <a href="NEWS.md">NEWS file</a> to summarize changes that affect
users.

## <a name="installation">📦 Installation</a>

### Install & Run with Docker

Run the official [Docker Image](https://hub.docker.com/r/ajslater/codex).
Instructions for running the docker image are on the Docker Hub README. This is
the recommended way to run Codex.

You'll then want to read the [Administration](#administration) section of this
document.

### Install & Run as a Native Application

You can also run Codex as a natively installed python application with pip.

#### Wheel Build Dependencies

You'll need to install these system dependencies before installing Codex.

##### macOS

<!-- eslint-skip -->

```sh
brew install jpeg libffi libyaml libzip openssl python unrar webp
```

##### Linux

###### <a href="#debian">Debian</a>

...and Ubuntu, Mint, MX and others.

<!-- eslint-skip -->

```sh
apt install build-essential libimagequant0 libjpeg62-turbo libopenjp2-7 libssl3 libyaml-0-2 libtiff6 libwebp7 python3-dev python3-pip mupdf unrar zlib1g
```

###### Alpine

<!-- eslint-skip -->

```sh
apk add bsd-compat-headers build-base jpeg-dev libffi-dev libwebp openssl-dev yaml-dev zlib-dev
```

##### Install unrar Runtime Dependency on non-debian Linux

Codex requires unrar to read CBR formatted comic archives. Unrar is often not
packaged for Linux, but here are some instructions:
[How to install unrar in Linux](https://www.unixtutorial.org/how-to-install-unrar-in-linux/)

Unrar as packaged for Alpine Linux v3.14 seems to work on Alpine v3.15+

#### Windows

Windows users should use Docker to run Codex until this documentation section is
complete.

Codex can _probably_ run on the Windows Linux Subsystem but I haven't personally
tested it yet. Try following the instructions for [Debian](#debian) above. There
may be outstanding platform related bugs.

Contributions to the Windows documentation will be gratefully accepted on
[the outstanding issue](https://github.com/ajslater/codex/issues/76) or Discord.

#### Install Codex with pip

You may now install Codex with pip

<!-- eslint-skip -->

```sh
pip3 install codex
```

#### Run Codex Natively

pip should install the codex binary on your path. Run

<!-- eslint-skip -->

```sh
codex
```

and then navigate to <http://localhost:9810/>

### Install & Run on your preexisting HomeAssistant server

If you have a [HomeAssistant](https://www.home-assistant.io/) server, Codex can
be installed with the following steps :

- Add the `https://github.com/alexbelgium/hassio-addons` repository by
  [clicking here](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Falexbelgium%2Fhassio-addons)
- Install the addon :
  [click here to automatically open the addon store, then install the addon](https://my.home-assistant.io/redirect/supervisor)
- Customize addon options, then then start the add-on.

## <a name="administration">👑 Administration</a>

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

<!-- eslint-skip -->

```sh
CODEX_RESET_ADMIN=1 codex
```

or, if using Docker:

<!-- eslint-skip -->

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

### PDFs

Codex only reads PDF metadata from the filename. If you decide to include PDFs
in your comic library, I recommend taking time to rename your files so Codex can
find some metadata. Codex recognizes several file naming schemes. This one has
good results:

`{series} v{volume} #{issue} {title} ({year}) {ignored}.pdf`

## <a name="configuration">🎛️ Configuration</a>

### Config Dir

The default config directory is `config/` directly under the working directory
you run codex from. You may specify an alternate config directory with the
environment variable `CODEX_CONFIG_DIR`.

The config directory contains a file named `hypercorn.toml` where you can
specify ports and bind addresses. If no `hypercorn.toml` is present Codex copies
a default one to that directory on startup.

The default values for the config options are:

<!-- eslint-skip -->

```toml
bind = ["0.0.0.0:9810"]
quick_bind = ["0.0.0.0:9810"]
root_path = "/codex"
```

The config directory also holds the main sqlite database, the Whoosh search
index, a Django cache and comic book cover thumbnails.

### Environment Variables

### Codex

- `LOGLEVEL` will change how verbose codex's logging is. Valid values are
  `ERROR`, `WARNING`, `INFO`, `DEBUG`. The default is `INFO`.
- `TIMEZONE` or `TZ` will explicitly set the timezone in long format (e.g.
  `"America/Los Angeles"`). This is useful inside Docker because codex cannot
  automatically detect the host machine's timezone.
- `CODEX_CONFIG_DIR` will set the path to codex config directory. Defaults to
  `$CWD/config`
- `CODEX_RESET_ADMIN=1` will reset the admin user and its password to defaults
  when codex starts.
- `CODEX_SKIP_INTEGRITY_CHECK=1` will skip the database integrity repair that
  runs when codex starts.
- `CODEX_LOG_DIR` sets a custom directory for saving logfiles. Defaults to
  `$CODEX_CONFIG_DIR/logs`
- `CODEX_LOG_TO_FILE=0` will not log to files.
- `CODEX_LOG_TO_CONSOLE=0` will not log to the console.

#### Comicbox

- `DEBUG_TRANSFORM` will show verbose information about how the comicbox library
  reads all archive metadata sources and transforms it into a the comicbox
  schema.

### Reverse Proxy

[nginx](https://nginx.org/) is often used as a TLS terminator and subpath proxy.

Here's an example nginx config with a subpath named '/codex'.

<!-- eslint-skip -->

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

<!-- eslint-skip -->

```toml
root_path = "/codex"
```

#### Nginx Reverse Proxy 502 when container refreshes

Nginx requires a special trick to refresh dns when linked Docker containers
recreate. See this
[nginx with dynamix upstreams](https://tenzer.dk/nginx-with-dynamic-upstreams/)
article.

### Restricted Memory Environments

Codex can run with as little as 1GB available RAM. Large batch jobs –like
importing and indexing tens of thousands of comics at once– will run faster the
more memory is available to Codex. The biggest gains in speed happen when you
increase memory up to about 6GB. Codex batch jobs do get faster the more memory
it has above 6GB, but with diminishing returns.

If you must run Codex in an admin restricted memory environment you might want
to temporarily give Codex a lot of memory to run a very large import job and
then restrict it for normal operation.

## <a name="usage">📖 Usage</a>

### 👤 Sessions & Accounts

Once your administrator has added some comic libraries, you may browse and read
comics. Codex will remember your preferences, bookmarks and progress in the
browser session. Codex destroys anonymous sessions and bookmarks after 60 days.
To preserve these settings across browsers and after sessions expire, you may
register an account with a username and password. You will have to contact your
administrator to reset your password if you forget it.

### 🗝️ API with Key Access

Codex has a limited number of API endpoints available with API Key Access. The
API Key is available on the admin/stats tab.

### ᯤ OPDS

Codex supports OPDS syndication and OPDS streaming. You may find the OPDS url in
the side drawer. It should take the form:

`http(s)://host.tld(:9810)(/root_path)/opds/v1.2/`

or

`http(s)://host.tld(:9810)(/root_path)/opds/v2.0/`

OPDS 2.0 support is experimental and not widely or well supported by clients.
OPDS 2.0 book readers exist, but I am not yet aware of an OPDS 2.0 comic reader.

#### Clients

- iOS has [Panels](https://panels.app/), [KYBook 3](http://kybook-reader.com/),
  and
  [Chunky Comic Reader](https://apps.apple.com/us/app/chunky-comic-reader/id663567628)
- Android has
  [Moon+](https://play.google.com/store/apps/details?id=com.flyersoft.moonreader)
  and
  [Librera](https://play.google.com/store/apps/details?id=com.foobnix.pdf.reader)

#### HTTP Basic Authentication

If you wish to access OPDS as your Codex User. You will have to add your
username and password to the URL. Some OPDS clients do not asssist you with
authentication. In that case the OPDS url will look like:

`http(s)://username:password@host.tld(:9810)(/root_path)/opds/v1.2/`

#### Supported OPDS Specifications

- [OPDS 1.2](https://specs.opds.io/opds-1.2.html)
- [OPDS-PSE 1.2](https://github.com/anansi-project/opds-pse/blob/master/v1.2.md)
- [OPDS Authentication 1.0](https://drafts.opds.io/authentication-for-opds-1.0.html)
- [OpenSearch 1.1](https://github.com/dewitt/opensearch)

## <a name="troubleshooting">🩺 Troubleshooting</a>

### 📒 Logs

Codex collects its logs in the `config/logs` directory. Take a look to see what
th e server is doing.

You can change how much codex logs by setting the `LOGLEVEL` environment
variable. By default this level is `INFO`. To see more verbose messages, run
codex like:

<!-- eslint-skip -->

```bash
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

If the database becomes corrupt, Codex includes a facitlity to rebuild the
database. Place a file named `rebuild_db` in your Codex config directory like
so:

<!-- eslint-skip -->

```sh
touch config/rebuild_db
```

Shut down and restart Codex.

The next time Codex starts it will back up the existing database and try to
rebuild it. The database lives in the config directory as the file
`config/db.sqlite3`. If this procedure goes kablooey, you may recover the
original database at `config/db.sqlite3.backup`.

## <a name="alternatives-to-codex">📚Alternatives</a>

- [Kavita](https://www.kavitareader.com/) has light metadata filtering/editing,
  supports comics, eBooks, and features for manga.
- [Komga](https://komga.org/) has light metadata editing.
- [Ubooquity](https://vaemendis.net/ubooquity/) reads both comics and eBooks.
- [Mylar](https://github.com/mylar3/mylar3) is the best comic book manager which
  also has a built in reader.
- [Comictagger](https://github.com/comictagger/comictagger) is a comic metadata
  editor. It comes with a powerful command line and desktop GUI.

## <a name="contributing">🤝 Contributing</a>

### <a name="bug_reports">🐛 Bug Reports</a>

Issues and feature requests are best filed on the
[Github issue tracker](https://github.com/ajslater/codex/issues).

### <a name="out-of-scope">🚫 Out of Scope</a>

- I have no intention of making this an eBook reader.
- I think metadata editing would be better placed in a comic manager than a
  reader.

### <a name="develop-codex">🛠 Develop</a>

Codex is a Django Python webserver with a VueJS front end.

`/codex/codex/` is the main django app which provides the webserver and
database.

`/codex/frontend/` is where the vuejs frontend lives.

Most of Codex development is now controlled through the Makefile. Type `make`
for a list of commands.

## <a name="discord">💬 Support</a>

By the generosity of the good people of
[Mylar](https://github.com/mylar3/mylar3), I and other Codex users answer
questions on the [Mylar Discord](https://discord.gg/6UG94R7E8T). Please use the
`#codex-support` channel to ask for help with Codex.

## <a name="links">🔗 Links</a>

- [Docker Image](https://hub.docker.com/r/ajslater/codex)
- [PyPi Package](https://pypi.org/project/codex/)
- [GitHub Project](https://github.com/ajslater/codex/)

## <a name="special-thanks">🙏🏻 Special Thanks</a>

- Thanks to [Aurélien Mazurie](https://pypi.org/user/ajmazurie/) for allowing me
  to use the PyPi name 'codex'.
- Thanks to the good people of
  [#mylar](https://github.com/mylar3/mylar3#live-support--conversation) for
  continuous feedback and comic ecosystem education.

## <a name="enjoy">😊 Enjoy</a>

![These simple people have managed to tap into the spiritual forces that mystics and yogis spend literal lifetimes seeking. I feel... ...I feel...](strange.jpg)
