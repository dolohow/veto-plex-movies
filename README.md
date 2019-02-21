Veto Plex Movies
================

Allows you to vote veto against removal of Plex movies and series.

It is especially useful if you share your Plex library with your friend and
you are not sure if removing movie or series will make them angry ;)

![Screencast](https://i.imgur.com/jIxi3M1.gif "Screencast")


## Installation
You need Python 3 to run this program.  It can now on Python 2, but I
did not make any effort to support that.

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
`screen`, `tmux` or `nohup`, like this:

```
nohup python poll.py &
```
