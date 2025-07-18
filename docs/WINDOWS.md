# 🪟 Codex Native Windows Installation

Windows users are encouraged to use Docker to run Codex, but it will also run
natively on the Windows Subsystem for Linux.

## Install or Upgrade WSL

[Use Microsoft's instructions to install the WSL](https://learn.microsoft.com/en-us/windows/wsl/install).
If you have previously installed WSL 1, you will have the best luck
[upgrading it to WSL 2](https://learn.microsoft.com/en-us/windows/wsl/install#upgrade-version-from-wsl-1-to-wsl-2)
and using the most recently supported Ubuntu version.

## Install Codex Dependencies

Ensure python3 & pip3 are installed in the WSL:

<!-- eslint-skip -->

```sh
apt install python3-pip
```

### Ubuntu Linux Dependencies

The WSL, by default is an Ubuntu Linux distribution, which is a variety of
Debian Linux. Open a shell in the WSL and use the Debian Linux dependency
instructions reproduced below:

<!-- eslint-skip -->

```sh
apt install build-essential libimagequant0 libjpeg-turbo8 libopenjp2-7 libssl libyaml-0-2 libtiff6 libwebp7 python3-dev python3-pip mupdGf unrar zlib1g
```

Versions of packages like libjpeg, libssl, libtiff may differ between flavors
and versions of your distributionG. If the package versions listed in the
example above are not available, try searching for ones that are with
`apt-cache` or `aptitude` if it is installed.

<!-- eslint-skip -->

```sh
apt-cache search libjpeg-turbo
```

## Install Codex

### Install Codex with pip for the whole system

When you have installed the dependandancies for your platform, you may now
install Codex with pip

<!-- eslint-skip -->

```sh
pip3 install codex --break-system-packages
```

### Install Codex with pip in a python virtual environment

Alternatively, if possibly overriding system packages in the WSL would not be
good for you, you may create a
[python virtual environment](https://docs.python.org/3/library/venv.html) that
will be separate from the system. In the following example `.venv` is the name
of the virtual environment, a directory where python will place an entire python
environment separate from the system python environment. You can name this
directory anything and place it anywhere you like. This directory is
traditionally lead with a dot so it becomes a hidden directory but that is not
required.

<!-- eslint-skip -->

```sh
sudo apt update
sudo apt install libpython3-dev
sudo apt install python3-venv
mkdir codex
cd codex
python -m venv .venv
```

Now you must activate the virtual environment:

<!-- eslint-skip -->

```sh
source .venv/bin/activate
```

Once you have activated the virtual environment you may install codex and it's
python dependencies in the virtual environment.

<!-- eslint-skip -->

```sh
pip3 install codex
```

To run Codex you will have to have this virtual environment activated. So in the
future if you create a new shell to start codex, you must source the activate
script again above before running Codex.

It seems the codex script maye also be installed to `$HOME/.local/bin` which is
not usually on the executable search path. To add this directory to the path:

<!-- eslint-skip -->

```sh
export PATH=$PATH:$HOME/.local/bin
```

You will probably want to add this line to your `$HOME/.bashrc` or
`$HOME/.profile` file to execute it every time you start a Linux shell.

## Mounting Network Drives on WSL

If your comics are on another machine, mounting network drives with the Samba 3
driver may avoid problems that may occur if you mount drives with the DrvFs or
CIFS drivers.

To mount a drive from server named `server` to the /mnt/comics directory once
for this session:

<!-- eslint-skip -->

```sh
sudo mount -t smb3 //server/comics /mnt/comics -o vers=3.1.1,defaults,username='comics',password='password'
```

To mount the drive every time WSL starts up edit the `/etc/fstab` file with a
line similar to:

<!-- eslint-skip -->

```sh
# file system   dir         type options                                        dump pass
//server/comics /mnt/comics smb3 vers=3.1.1,username='comics',password='comics' 0 0
```

### Illegal Characters in Samba Network Drives

Network filesystems may contain characters that are illegal under Windows such
as `\ / : * ? " < > |` or special unicode or other character encodings. The
Samba driver will mangle these for presentation, often substituting a `?`
character for the illegal character. The simplest solution for these files is to
rename the files.

But it may
[also be possible](https://serverfault.com/questions/124611/special-characters-in-samba-filenames)
to add a `iocharset=iso8859-1` to the mount options and achieve some success. If
this works for you please report it so I can update this documentation.

## Run Codex

Return to the Main [README](README.md#administration) for help running and
administering Codex.

## Special Thanks

- To [ProfessionalTart](https://github.com/professionaltart) for providing the
  majority of these instructions.
