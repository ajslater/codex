# Codex

Codex is a comic archive browser and reader.

## <a name="features">✨ Features</a>

- Codex is a web server, not a desktop or mobile app.
- Per user bookmarking. You get per browser bookmarks even before you make an account.
- Filter and sort on all comic metadata and unread status per user.
- Browse a tree of publishers, imprints, series, volumes, or your own folder hierarchy.
- Read comics in a variety of aspect ratios that fit your screen.
- Watches the filesystem and automatically imports new or changed comics.

## <a name="demonstration">📖 Demonstration</a>

You may browse a [live demo server](https://codex.sl8r.net/) to get a feel for Codex.

## <a name="news">📰 News</a>

Codex has a <a href="NEWS.md">NEWS file</a> to summarize changes that affect users.

## <a name="installation">📦 Installation</a>

### Install & Run with Docker

All dependencies are bundled in the official [Docker Image](https://hub.docker.com/r/ajslater/codex). Instructions for running the docker image are on the Docker Hub README. This is the recommended way to run Codex.

You'll then want to read the [Administration](#administration) section of this document.

### Install & Run as a Native Application

You can also run Codex as a natively installed python application with pip.

#### Wheel Build Dependencies

You'll need to install these system dependencies before installing Codex.

##### macOS

```sh
brew install jpeg libffi libyaml libzip openssl python
```

##### Linux

###### Debian based (e.g. Ubuntu)

```sh
apt install build-essential libffi-dev libjpeg-dev libssl-dev libyaml-dev python3-pip zlib1g-dev
```

###### Alpine

```sh
apk add bsd-compat-headers build-base jpeg-dev libffi-dev openssl-dev yaml-dev zlib-dev
```

#### Install unrar Runtime Dependency

Codex requires unrar to read cbr formatted comic archives.

##### Linux

[How to install unrar in Linux](https://www.unixtutorial.org/how-to-install-unrar-in-linux/)

##### macOS

```sh
brew install unrar
```

#### Install Codex with pip

Finally, you may install Codex with pip

```sh
pip3 install codex
```

#### Run Codex Natively

pip should install the codex binary on your path. Run

```sh
codex
```

and then navigate to [http://localhost:9810/](http://localhost:9810/)

## <a name="administration">👑 Administration</a>

### Change the Admin password

The first thing you need to do is to log in as an Administrator and change the admin password.

- Log in with the **&vellip;** menu in the upper right of the browse view. The default administator username/password is admin/admin.
- Navigate to the Admin Panel by selecting it from under the three dots menu after you have logged in.
- Navigate to the Users panel.
- Select the `admin` user.
- Change the admin password using the tiny "this form" link in the password section.
- You may also change the admin user's name or anything else.

### Adding Comic Libraries

The second thing you should do is log in as an Administrator and add one or more comic libraries.

- Log in with any superuser (such as the default adimin account) using the **&vellip;** menu in the upper right of the browse view.
- Navigate to the Admin Panel by selecting it from under the three dots menu after you have logged in.
- Navigate to the Codex API Librarys (sic) on the Admin Panel
- Add a Library with the "ADD LIBRARY +" button in the upper right.

#### Reset the admin password.

If you forget all your superuser passwords, you may restore the original default admin account by running codex with the `CODEX_RESET_ADMIN` environment variable set.

```sh
CODEX_RESET_ADMIN=1 codex
```

or, if using Docker:

```sh
docker run -e CODEX_RESET_ADMIN=1 -v <host path to config>/config:/config ajslater/codex
```

## <a name="configuration">⚙️Configuration</a>

### Config Dir

The default config directory is named `config/` directly under the working directory you run codex from. You may specify an alternate config directory with the environment variable `CODEX_CONFIG_DIR`.

The config directory contains a hypercorn config `hypercorn.toml` where you can specify ports and bind addresses. If no `hypercorn.toml` is present a default one is copied to that directory on startup.

The default values for the config options are:

```toml
bind = ["0.0.0.0:9810"]
quick_bind = ["0.0.0.0:9810"]
root_path = "/codex"
max_db_ops = 100000

```

The config directory also holds the main sqlite database, a django cache and comic book cover thumbnails generated when comics are imported. Reimport a comic or an entire library to regenereate these cover thumbnails.

### Environment Variables

- `LOGLEVEL` will change how verbose codex's logging is. Valid values are `ERROR`, `WARNING`, `INFO`, `VERBOSE`, `DEBUG`. The default is `INFO`.
- `TIMEZONE` or `TZ` will explicitly the timezone in long format (e.g. `"America/Los Angeles"`). This is mostly useful inside Docker because codex cannot automatically detect the host machine's timezone.
- `CODEX_CONFIG_DIR` will set the path to codex config directory. Defaults to `$CWD/config`
- `CODEX_RESET_ADMIN=1` will reset the admin user and its password to defaults when codex starts.
- `CODEX_SKIP_INTEGRITY_CHECK` will skip the database integrity repair that runs when codex starts.

### Reverse Proxy

[nginx](https://nginx.org/) is often used as a TLS terminator and subpath proxy.

Here's an example nginx config with a subpath named '/codex'.

```nginx
    # HTTP
    proxy_set_header  Host              $http_host;
    proxy_set_header  X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header  X-Forwarded-Host  $server_name;
    proxy_set_header  X-Forwarded-Port  $server_port;
    proxy_set_header  X-Forwarded-Proto $scheme;
    proxy_set_header  X-Real-IP         $remote_addr;
    proxy_set_header  X-Scheme          $scheme;

    # Websockets
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade"

    # This example uses a docker container named 'codex' at sub-path /codex
    # Use a valid IP or resolvable host name for other configurations.
    location /codex {
        proxy_pass  http://codex:9810;
    }
```

Specify a reverse proxy sub path (if you have one) in the config/hypercorn.toml

```toml
root_path = "/codex"

```

#### Nginx Reverse Proxy 502 when container is refreshed.

Nginx requires a special trick to refresh dns when linked Docker containers
are recreated. See this [nginx with dynamix upstreams](https://tenzer.dk/nginx-with-dynamic-upstreams/) article.

## <a name="usage">📖 Usage</a>

### Sessions & Accounts

Once your administrator has added some comic libraries, you may browse and read comics. Codex will remember your preferences, bookmarks and progress in the browser session. Sessions last 60 days at which point they are destroyed.
To preserve these settings across browsers and after sessions expire, you may register an account with a username and password.
You will have to contact your administrator to reset your password if you forget it.

## <a name="troubleshooting">🩺 Troubleshooting</a>

### Logs

Codex collects its logs in the `config/logs` directory. Take a look to see what th e server is doing.

You can change how much codex logs by setting the `LOGLEVEL` environment variable. By default this level is `INFO`. To see more messages run codex like:

```bash
LOGLEVEL=VERBOSE codex
```

To see (probably too many) noisy messages try:

```bash
LOGLEVEL=DEBUG codex
```

### Watching Filesystem Events with Docker

Codex tries to watch for filesystem events to instantly update your Libraries when they are changed on disk. But these native filesystem events are not translated between macOS & Windows Docker hosts and the Docker Linux container. If you find that your installation is not updating to filesystem changes instantly, you might try enabling polling for the affected libraries and decreasing the `poll_every` value in the Admin console to a frequency that suits you.

### Emergency Database Repair

If the database becomes corrupt, Codex includes a facitlity to rebuild the database.
Place a file named `rebuild_db` in your Codex config directory like so:

```sh
  $ touch config/rebuild_db
```

Shut down and restart Codex.

The next time Codex starts it will back up the existing database and try to rebuild it.
The database lives in the config directory as the file `config/db.sqlite3`.
If this procedure goes kablooey, you may recover the original database at `config/db.sqlite3.backup`.

### Bulk Database Updates Fail

Codex's bulk database updater has been tested to usually work batching 100,000 filesystem events at a time. With enough RAM Codex could probably batch much more. But if you find that updating large batches of comics are failing, consider setting a the `max_db_ops` value in `hypercorn.toml` to a lower value. 1000 will probably still be pretty fast, for instance.

### Bug Reports

Issues are best filed [here on github](https://github.com/ajslater/codex/issues).
However I and other brave Codex testers may also sometimes be found on IRC in the [Mylar support channels](https://github.com/mylar3/mylar3#live-support--conversation).

## <a name="roadmap">🚀 Roadmap</a>

### Next Up

1. Full text search
2. [OPDS API](https://en.wikipedia.org/wiki/Open_Publication_Distribution_System)

### Out of Scope

- I have no intention of making this an eBook reader like [Ubooquity](https://vaemendis.net/ubooquity/).
- I am not interested in this becoming a sophisticated comic manager like [Mylar](https://github.com/mylar3/mylar3). I am also thinking more and more that metadata editing belongs in a manager and not in a reader like Codex.

## <a name="alternatives-to-codex">📚Alternatives</a>

- [Komga](https://komga.org/) has light metadata editing and full text search of metadata.
- [Ubooquity](https://vaemendis.net/ubooquity/) is a good looking comic webserver. It also reads eBooks.
- [Mylar](https://github.com/mylar3/mylar3) is probably the best comic book manager and also has a built in reader.
- [Comictagger](https://github.com/comictagger/comictagger) is not really a reader, but seems to be the best comic metadata editor. It comes with a powerful command line and useful desktop GUI.

## <a name="develop-codex">🛠 Develop</a>

Codex is a Django Python webserver with a VueJS front end. This is my first ever Javascript frontend. In retrospect I wish I'd known about FastAPI when I started, that looks nice. But I'm pretty satisfied with VueJS.

`/codex/codex/` is the main django app which provides the webserver and database.

`/codex/frontend/` is where the vuejs frontend lives.

`/codex/setup-dev.sh` will install development dependencies.

`/codex/dev-server-ttabs.sh` will run the three or four different servers recommended for development in terminal tabs.

`/codex/run.sh` runs the main Django server. Set the `DEBUG` environment variable to activate debug mode: `DEBUG=1 ./run.sh`. This also lets you run the server without collecting static files for production and with a hot reloading frontend.

### Links

- [Docker Image](https://hub.docker.com/r/ajslater/codex)
- [PyPi Package](https://pypi.org/project/codex/)
- [GitHub Project](https://github.com/ajslater/codex/)

## <a name="special-thanks">🙏🏻 Special Thanks</a>

- Thanks to [Aurélien Mazurie](https://pypi.org/user/ajmazurie/) for allowing me to use the PyPi name 'codex'.
- Thanks to the good people of [#mylar](https://github.com/mylar3/mylar3#live-support--conversation) for continuous feedback and comic ecosystem education.

## <a name="enjoy">Enjoy!</a>

![These simple people have managed to tap into the spiritual forces that mystics and yogis spend literal lifetimes seeking. I feel... ...I feel...](strange.jpg)
