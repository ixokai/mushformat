mushformat
==========

Yet Another MUSHCode unformatter

What the hell is MUSHCode?
==========================

If you need to ask, you really don't want to know. Consider it a kind of masochism. This is an attempt to make it slightly less awful.

Why?
====

There's a few options for MUSHCode unformatters out there, but none quite fit my workflow -- or I just wanted to add some more features, and didn't feel like writing some perl. So, I made my own.

Features
========

- Takes "raw" or formatted MUSHCode and 'compiles' it into the compressed, line-noise version that the MUSH servers want. Obviously.
- Allows you to take multiple source files to compile them into a single output file for better organization
- Allows you to speciy "defines" either in a config file, the command line, or in source files; these are search/replace operations like a #DEFINE macro in C/C++. You can use this to store certain game-specific configuration like the objects you want to write to.
- Quoting: lines that begin and end with a doublequote (") preserve their spaces and newlines to allow you to insert ASCII art and similar things.
- Can connect to and directly install / upgrade code (from both source and compiled forms)
- (Pending) Integrates with RhostMUSH's @snapshot system to semi-automatically backup / restore systems.
- ... dunno!

Obtaining
=========

mushformat is currently only provided for Windows in a 'compiled' form, but that's because I am lazy. I can build for Linux or OSX if someone wants, but otherwise it can be run from source easily. It requires:

- Python 3.4
- Tkinter (for those linux distributions that distribute Tk separately) -- and before anyone asks, no, I don't like Tk. I don't like it at all. But, its the smallest and most crossplatform I could find easily -- PyQt is just SO BIG, for such a small app it doesn't make sense.
- docopt

Usage
=====

...

Formatting Rules
================

mushformat follows, basically, the 'standard' mush unformatter rules. Its general purpose is to discard whitespace and combine multiple lines into a single MUSH line. This 'pretty' formatting is easy to read, but when run through an 'unformatter' (as this is) produce proper MUSHCode. 

1. Lines that begin with '#:' are compiler directives and are discarded after processing
2. Blank lines, lines that start with '#', and lines that start with '@@' are discarded.
3. Lines that beginw tih '#:' are directives, see below.
4. A '-' on a line by itself, or at the start of a line, ends an existing MUSH line.
5. Any non-whitespace character on the first column ends an existing MUSH line. 
6. A tab character is treated as 8 spaces.
7. If a line begins and ends with a ", it is a quoted line. A quoted line follows different rules:
  7.1. At the end of a quoted line, a newline (%r) is added unless the line ends with \ (BEFORE the finishing ")
  7.2. A quoted line preserves but compresses all spaces within it; where there are more then 4 spaces in a run, the space() function is used. Otherwise, for space runs greater then 2, they are replaced by %b codes.
8. Leading whitespace on a line indicates a continuation of a previous MUSH line. This whitespace is DISCARDED. 

Directives
==========

The currently supported directives are:

- #:DEFINE <name> <value> -- Mimics -D <name>=<value> on the command line, but is always set for this file.

Configuration
=============

There are two configuration files used by mushformat: host.ini and project.ini
