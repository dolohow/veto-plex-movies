Veto Plex Movies
================

Allows you to vote veto against removal of Plex movies and series.

It is especially useful if you share your Plex library with your friend and
you are not sure if removing movie or series will make them angry ;)

![Screencast](https://i.imgur.com/jIxi3M1.gif "Screencast")


## Installation
You need at least Python 3.6 to run this program.
```
pip install -r requirements.txt
```

Create configuration file file
```
cp poll.ini.template poll.ini
```

Edit it and save.


## Run
Quick check:
```
python poll.py
```

If you want it to run in background, which is advisable.  You can use

```
python poll.py -d
```

It is also good idea to run it with `systemd`.
