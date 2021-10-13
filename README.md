# Codex

Codex is a comic archive browser and reader.

## <a name="features">Features</a>

- A web server, not a desktop or mobile app.
- Per user bookmarking. Bookmarks even if you don't make an account.
- Filter and sort on all comic metadata and unread status per user.
- Browse a tree of Publisher, Imprints, Series and Volumes, or your own folder hierarchy.
- Watches the filesystem and automatically imports new or changed comics.

## <a name="state-of-development">State of Development</a>

Codex is in alpha test. It has not received widespread testing.
[Please file bug reports on GitHub.](https://github.com/ajslater/codex/issues) It is still possible that the data model might change enough that subsequent versions might require a database reset.

## <a name="demonstration">Demonstration</a>

You may browse a [live demo server](https://codex.sl8r.net/) on a very small VPS, with no CDN.

## <a name="install-and-run-codex">Install and Run Codex</a>

### Install & Run with Docker

All dependancies are bundled in the official [Docker Image](https://hub.docker.com/r/ajslater/codex). Instructions for running the docker image are on the Docker Hub README. This is the recommended way to run Codex.

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

#### Install unrar Runtime Dependancy

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

## <a name="administration">Administration</a>

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

## <a name="configure-codex">Configure Codex</a>

### Config Dir

The default config directory is named `config/` directly under the working directory you run codex from. You may specificy an alternate config directory with the environment variable `CODEX_CONFIG_DIR`.

The config directory contains a hypercorn config `hypercorn.toml` where you can specify ports and bind addresses. If no `hypercorn.toml` is present a default one is copied to that directory on startup. The default port is 9810.

The config directory also holds the main sqlite database, a django cache and comic book cover thumbnails generated when comics are imported. Reimport a comic or an entire library to regenereate these cover thumbnails.

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

## <a name="using-codex">Using Codex</a>

### Sessions & Accounts

Once your administrator has added some comic libraries, you may browse and read comics. Codex will remember your preferences, bookmarks and progress in the browser session. Sessions last 60 days at which point they are destroyed.
To preserve these settings across browsers and after sessions expire, you may register an account with a username and password.
You will have to contact your administrator to reset your password if you forget it.

## <a name="troubleshooting">Troubleshooting</a>

### Logs

Codex collects its logs in the `config/logs` directory. Take a look to see what th e server is doing.

### LOGLEVEL

You can change how much codex logs by setting the LOGLEVEL environment variable. By default this level is "INFO". To see more, noisy messages run codex like:

```bash
LOGLEVEL=DEBUG codex
```

### Emergency Database Repair

If the database becomes corrupt, Codex includes a facitlity to rebuild the database.
Place a file named `rebuild_db` in your Codex config directory like so:

```sh
  $ touch config/rebuild_db
```

Shut down and restart Codex.

The next time Codex starts it will back up the exisiting database and try to rebuild it.
The database lives in the config directory as the file `config/db.sqlite3`.
If this procedure goes kablooey, you may recover the original database at `config/db.sqlite3.backup`.

### Bug Reports & Feature Requests

Issues are best filed [here on github](https://github.com/ajslater/codex/issues).
However I and other brave Codex alpha testers may also be found on IRC in the [#mylar](irc://chat.freenode.net/mylar) channel.

## <a name="roadmap">Roadmap</a>

### Next Up

1. Edit & write metadata for comics
2. Full text search
3. [OPDS API](https://en.wikipedia.org/wiki/Open_Publication_Distribution_System)

## <a name="out-of-scope">Out of Scope</a>

- I have no intention of making this an eBook reader like [Ubooquity](https://vaemendis.net/ubooquity/).
- I am not interested in this becoming a sophisticated comic manager like [Mylar](https://github.com/mylar3/mylar3)

## <a name="alternatives-to-codex">Alternatives to Codex</a>

- [Komga](https://komga.org/) has light metadata editing and full text search of metadata.
- [Ubooquity](https://vaemendis.net/ubooquity/) is a good looking comic webserver. It also reads eBooks.

## <a name="develop-codex">Develop Codex</a>

Codex is a Django Python webserver with a VueJS front end. This is my first ever Javascript frontend. In retrospect I wish I'd known about FastAPI when I started, that looks nice. But I'm pretty satisfied with VueJS.

`/codex/codex/` is the main django app which provides the webserver and database.

`/codex/frontend/` is where the vuejs frontend lives.

`/codex/setup-dev.sh` will install development dependancies.

`/codex/dev-server-ttabs.sh` will run the three or four different servers reccomended for development in terminal tabs.

`/codex/run.sh` runs the main Django server. Set the `DEBUG` environment variable to activate debug mode: `DEBUG=1 ./run.sh`. This also lets you run the server without collecting static files for production and with a hot reloading frontend.

### Links

- [Docker Image](https://hub.docker.com/r/ajslater/codex)
- [PyPi Package](https://pypi.org/project/codex/)
- [GitHub Project](https://github.com/ajslater/codex/)

## <a name="special-thanks">Special Thanks</a>

- Thanks to [Aurélien Mazurie](https://pypi.org/user/ajmazurie/) for allowing me to use the PyPi name 'codex'.
- Thanks to the good people of [#mylar](irc://chat.freenode.net/mylar) for continuous feedback and comic ecosystem education.

## <a name="enjoy">Enjoy!</a>

![These simple people have managed to tap into the spiritual forces that mystics and yogis spend literal lifetimes seeking. I feel... ...I feel...](strange.jpg)
