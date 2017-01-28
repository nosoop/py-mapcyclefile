# py-mapcyclefile

(Note:  While it's probably still usable, I effectively stopped maintaining this script.)

To be more in line with UNIX philosophy, I wrote a "replacement" utility that only serves the purpose of dumping Workshop map information to standard output.  It's meant to be chained with other tools instead of an all-in-one system.

[The script is available as a gist here.](https://gist.github.com/nosoop/6f8065df2aa81573ab8ba7d2cee65a86)

----
## About

A utility to modify and check SRCDS mapcycle files.  (Mainly written for TF2.)

It gets tedious to look for a workshop map, take reference of its ID, then add / remove it from whichever mapcycles you are looking to modify.  CS:GO has `host_workshop_collection`.  TF2 doesn't really have any native equivalent.

With this script (running as a scheduled task), updating a mapcycle with workshop maps is condensed to a two-click add / remove process.

## Features
* Configuration backups.  On `--backup`, the script copies the existing mapcycle file to a `mapcycle_backups` subdirectory if there was any modification to the current one.
* Multiple collections support.  Nice to have if you want to just automatically pull down maps from other users' collections, too, and even if their collection is a mix of maps and other workshop content (this script ignores non-map content).
* Tag inclusion / exclusion.  Get multiple mapcycle files out of just one collection!
* A more silent operation mode.  On `--quiet`, the script only spits out a message on changes (perfect for not getting blasted through cron).
* Deduplication.  With `--list-duplicates`, the script can tell you if two or more maps partially share names.  Useful to see if you added in a Workshop map and forgot to remove a standard custom map, or if you have multiple versions of a map in your mapcycle.

## Installation
1.  Fulfill the prerequisites:
  * Install Python3, if you haven't.  And `pip` for Python3.
  * Also install the `requests` library for Python3:  `pip3 install requests`.
  * Obtain a Steam Web API key from [this page](https://steamcommunity.com/dev/apikey).  Pass it to the application through the `--api-key` command line argument or as the environment variable `$STEAM_API_KEY`.
  * If you're interested in syncing a collection and you haven't created one yet, sign into Steam and create [a new TF2 collection](https://steamcommunity.com/workshop/editcollection/?appid=440).
2.  Save a copy of the `mapcyclefile.py` script somewhere and launch it.

Assuming you have shell access to a server, it's preferable to install it there, but it *should* work on any other machine; you just have to copy the config back over.
