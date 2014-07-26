# Copyright (c) 2014 Stephen Hansen
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""mushformat

Usage:
    mushformat compile [-O OUTPUT] [-D NAME=VALUE ...] [--defines PATH] [SOURCE ...]
    mushformat define [NAME VALUE | --name=NAME --value=VALUE] [--defines PATH]
    mushformat define --list [--defines PATH]
    mushformat define --delete NAME [--defines PATH]
    mushformat install (-S SOURCE | -O OUTPUT) -H HOSTINI [ -D NAME=VALUE ...] [--defines PATH]



Options:
  -D NAME=VALUE  Set a define for only this compilation.
  --defines PATH  The path to a defines.json file; if set to off, no defines will be used. [default: .]

Credit:
  mushformat is written by Stephen Hansen (aka, ixokai)
  Based on mpp.pl by Alan "Javelin" Schwartz, which was in turn based on mpp.c by Joshua Bell.
"""

# Compilation Rules:
#
#     1) Lines that start with #: are compiler directives and are processed
#        then skipped.
#     2) Blank lines, lines that start with # and lines that start with @@ are
#        removed.
#     3) A - on a line by itself, or at the start of a line, is converted into
#        a %r
#     4) Any non-whitespace character in the first column indicates a new line
#        of code
#     5) If a line starts AND ends with ", it will be compressed but whitespace
#        preserved. If it ends with \" the trailing %r will be skipped.
#        Tab characters are treated as 8 spaces in quote mode.
#     6) Leading whitespace on a line indicates a continuation of the previous line
#
# Directives:
#
#       #:SEARCH JGO=Job Global Object <JGO>
#           Only valid during install actions. Performs a search for "Job Global Object <JGO>" and
#           adds it to the installation defines.


__VERSION__ = "0.1"

import os
import re
import sys
import json
import glob

from docopt import docopt
from tkinter import Tk, filedialog

class DefineHandler:
    def __init__(self, arguments):
        self.arguments = arguments
        defines = arguments["--defines"]
        if defines == "off":
            self.defines_file = None
        else:
            self.defines_file = os.path.join(defines)
            if os.path.isdir(self.defines_file):
                self.defines_file = os.path.join(self.defines_file, "defines.json")

    def _get_current(self):
        if self.defines_file is None:
            return {}

        try:
            with open(self.defines_file, "rU") as defines_file:
                return json.load(defines_file)
        except FileNotFoundError:
            return {}

    current_defines = property(_get_current)

    def set(self, key, value):
        if self.defines_file is None:
            return print("mushformat: defines disabled")

        current_defines = self.current_defines
        current_defines[key] = value

        with open(self.defines_file, "w") as defines_file:
            json.dump(current_defines, defines_file)

        print("mushformat: defined '{}' as '{}'".format(key, value))

    def list(self):
        if self.defines_file is None:
            return print("mushformat: defines disabled")

        current_defines = self.current_defines

        if not current_defines:
            print("mushformat: no defines set")
        else:
            print("mushformat: current defines are:")
            for key, value in current_defines.items():
                print("\t'{}' = '{}'".format(key, value))

            print("mushformat: end.")

    def delete(self):
        if self.defines_file is None:
            return print("mushformat: defines disabled")

        current_defines = self.current_defines
        key = self.arguments["NAME"]
        if key in current_defines:
            del current_defines[key]

            with open(self.defines_file, "w") as defines_file:
                json.dump(current_defines, defines_file)

            print("mushformat: '{}' is no longer defined.".format(key))
        else:
            print("mushformat: '{}' is not currently defined.".format(key))

    def main(self):
        if self.arguments["NAME"] and self.arguments["VALUE"]:
            self.set(self.arguments["NAME"], self.arguments["VALUE"])

        elif self.arguments["--name"] and self.arguments["--value"]:
            self.set(self.arguments["--name"], self.arguments["--value"])

        elif self.arguments["--list"]:
            self.list()

        elif self.arguments["--delete"]:
            self.delete()


class CompileHandler:
    def __init__(self, arguments):
        self.arguments = arguments
        self.define_handler = DefineHandler(arguments)
        self.current_defines = self.define_handler.current_defines

        for item in arguments["-D"]:
            if "=" not in item:
                print("mushformat: -D expects KEY=VALUE, got '{}'".format(item))
                sys.exit(1)

            key, value = [x.strip() for x in item.split("=", 1)]
            self.current_defines[key] = value

    def main(self):
        source_paths = self.arguments["SOURCE"]
        output_path = self.arguments["OUTPUT"]

        if not source_paths:
            source_paths = filedialog.askopenfilenames(title="Select MUSH Source files?")
            if not source_paths:
                return

        if not output_path:
            output_path = filedialog.asksaveasfilename(title="Save compiled MUSHCode to?")
            if not output_path:
                return

        source_paths = [os.path.abspath(p) for p in source_paths]
        output_path = os.path.abspath(output_path)

        self.compile(source_paths, output_path)

    def do_directive(self, directive):
        if directive[0].lower() == "define":
            try:
                self.current_defines[directive[1]] = directive[2]
            except IndexError:
                print("Directive '{}' invalid.".format(' '.join(directive)))
                sys.exit(2)

    def _space_compress(self, match):
        length = len(match.group(0))
        if length == 1:
            return " "
        elif length < 5:
            return "%b" * length
        else:
            return "[space({})]".format(length)

    def do_quote(self, line):
        output = []

        if "\t" in line:
            line = line.replace("\t", " " * 8)

        line = re.sub("\s{2,}", self._space_compress, line)

        output.append(line)

        if not line.endswith("\\"):
            output.append("%r")

        return "".join(output)

    def compile(self, source_paths, output_path):
        with open(output_path, "w") as output_file:
            for source_path in source_paths:
                with open(source_path, "rU") as source_file:
                    for line in source_file:
                        if line.endswith("\n"):
                            line = line[:-1]

                        if line.startswith("#:"):
                            self.do_directive(line[2:].split(" "))
                            continue

                        if line.startswith("@@") or line.startswith("#"):
                            continue

                        if not line.strip():
                            continue

                        for define, replacement in self.current_defines.items():
                            if define in line:
                                line = line.replace(define, replacement)

                        if line.startswith('"') and line.endswith('"'):
                            output_file.write(self.do_quote(line[1:-1]))
                            continue

                        if line.strip() == "-":
                            output_file.write("\n")
                            continue
                        elif line.startswith("-"):
                            output_file.write("\n")
                            line = line[1:]

                        if not line[0].isspace():
                            output_file.write("\n")

                        output_file.write(line.strip())

                    output_file.write("\n")


class InstallHandler:
    def __init__(self, arguments):
        self.arguments = arguments

        print("mushformat: installation is actually a planned but not actually done feature. erp!")
        sys.exit(4)



def main():
    if not sys.argv[1:]:
        sys.argv = [sys.argv[0], "compile"]

    arguments = docopt(__doc__, version="mushformat {}".format(__VERSION__))
    handler = None

    root = Tk()
    root.withdraw()

    if arguments["define"]:
        handler = DefineHandler(arguments)
    elif arguments["compile"]:
        handler = CompileHandler(arguments)
    elif arguments["install"]:
        handler = InstallHandler(arguments)

    if handler:
        handler.main()


if __name__ == "__main__":
    main()