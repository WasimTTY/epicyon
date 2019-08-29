<img src="https://code.freedombone.net/bashrc/epicyon/raw/master/img/logo.png?raw=true" width=256/>

A minimal ActivityPub server.

[Commandline interface](README_commandline.md).

[W3C Specification](https://www.w3.org/TR/activitypub)

Includes emojis designed by [OpenMoji](https://openmoji.org) – the open-source emoji and icon project. License: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0)

## Goals

 * A minimal ActivityPub server, comparable to an email MTA
 * AGPLv3+
 * Server-to-server and client-to-server protocols supported
 * Implemented in a common language (Python 3)
 * Keyword filtering.
 * Remove metadata from attached images, avatars and backgrounds
 * Being able to build crowdsouced organizations with roles and skills
 * Sharings collection, similar to the gnusocial sharings plugin
 * Quotas for received posts per day, per domain and per account
 * Hellthread detection and removal
 * Instance and account level federation lists
 * Support content warnings, reporting and blocking
 * http signatures and basic auth
 * Compatible with http (onion addresses), https and dat
 * Minimal dependencies.
 * Capabilities based security
 * Support image blurhashes
 * Data minimization principle. Configurable post expiry time
 * Likes and repeats only visible to authorized viewers
 * ReplyGuy mitigation - maxmimum replies per post or posts per day
 * Ability to delete or hide specific conversation threads
 * Commandline interface
 * Simple web interface
 * Designed for intermittent connectivity. Assume network disruptions
 * Limited visibility of follows/followers
 * Suitable for single board computers

## Features which won't be implemented

The following are considered antifeatures of other social network systems, since they encourage dysfunctional social interactions.

 * Trending hashtags, or trending anything
 * Ranking, rating or recommending mechanisms for posts or people (other than likes or repeats/boosts)
 * Geolocation features
 * Algorithmic timelines (i.e. non-chronological)
 * Direct payment mechanisms, although integration with other services may be possible
 * Any variety of blockchain
 * Sponsored posts

## Install

On Arch/Parabola:

``` bash
sudo pacman -S tor python-pip python-pysocks python-pycryptodome python-beautifulsoup4 imagemagick python-pillow python-numpy python-dateutil
sudo pip install commentjson
```

Or on Debian:

``` bash
sudo apt-get -y install tor python3-pip python3-socks imagemagick python3-numpy python3-setuptools python3-crypto python3-dateutil python3-pil.imagetk
sudo pip3 install commentjson beautifulsoup4 pycryptodome
```

## Running Tests

To run the unit tests:

``` bash
python3 epicyon.py --tests
```

To run the network tests. These simulate instances exchanging messages.

``` bash
python3 epicyon.py --testsnetwork
```


## Running the Server

To run with defaults:

``` bash
python3 epicyon.py
```

In a browser of choice (but not Tor browser) you can then navigate to:

``` text
http://localhost:8085/users/admin
```

If it's working then you should see the json actor for the default admin account.

For a more realistic installation you can run on a defined domain and port:

``` bash
python3 epicyon.py --domain [name] --port 8000 --https
```

You will need to proxy port 8000 through your web server and set up CA certificates as needed.

By default data will be stored in the directory in which you run the server, but you can also specify a directory:

``` bash
python3 epicyon.py --domain [name] --port 8000 --https --path [data directory]
```


## Culling follower numbers

In this system the number of followers which an account has will only be visible to the account holder. Other viewers will see a made up number. Which accounts are followed or followed by a person will also only have limited visibility.

The intention is to prevent the construction of detailed social graphs by adversaries, and to frustrate attempts to build celebrity status based on number of followers, which on sites like Twitter creates a dubious economy of fake accounts and the trading thereof.

If you are the account holder though you will be able to see exactly who you're following or being followed by.


## Object Capabilities Security

A description of the proposed object capabilities model [is here](ocaps.md).

## Customizations

You can customize the terms of service by editing **accounts/tos.txt**. If it doesn't already exist then you can use **default_tos.txt** as a template.

On the login screen you can provide a custom welcome message by creating the file **accounts/login.txt**. This could be used to show a motd or scheduled maintenance information.

You can customize the image on the login screen by saving your instance logo to **accounts/login.png**. A background image can also be set for the login screen by adding **accounts/login-background.png**

A custom background image can be supplied for the search screen by adding **accounts/search-background.png**

When a moderator report is created the message at the top of the screen can be customized to provide any additional information, advice or alerts. Edit **accounts/report.txt** and add your text.

Extra emoji can be added to the *emoji* directory and you should then update the **emoji/emoji.json** file, which maps the name to the filename (without the .png extension).

