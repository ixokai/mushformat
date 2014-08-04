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
    mushformat compile [-O OUTPUT | --clipboard] [-D NAME=VALUE ...] [--defines PATH] [--match PATTERN] [SOURCE ...]
    mushformat compile -P PROJECT [-D NAME=VALUE ...] [--defines PATH]
    mushformat define [NAME VALUE | --name=NAME --value=VALUE] [--defines PATH]
    mushformat define --list [--defines PATH]
    mushformat define --delete NAME [--defines PATH]
    mushformat install (-S SOURCE ... | -C COMPILED ... | -P PROJECT) -H HOSTCFG [ -D NAME=VALUE ...] [--defines PATH] [--match PATTERN]

Options:
  -S SOURCE  For install, file to read raw MUSHcode from
  -O OUTPUT  For compile, File to write compiled MUSHCode to; for install, file to read compiled MUSHcode from.
  -D NAME=VALUE  Set a define for only this compilation.
  --defines PATH  The path to a defines.json file; if set to off, no defines will be used. [default: .]
  --match PATTERN  Only lines which match the specified regex pattern (automatically rooted at the beginning) will be written out
  -P PROJECT  Compile or install the project specified in the given project.yaml file.
  -H HOSTCFG  The specified host.yaml will specify the connection and authorization information for installation

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
#     7) On a line, any text after #// is discarded.
#
# Directives:
#
#       #:SEARCH JGO=Job Global Object <JGO>
#           Only valid during install actions. Performs a search for "Job Global Object <JGO>" and
#           adds it to the installation defines.


__VERSION__ = "0.2"

import io
import os
import re
import sys
import time
import glob
import random
import string
import telnetlib

import yaml
import pyperclip

from docopt import docopt
from tkinter import Tk, filedialog, messagebox


class DefineHandler:
    def __init__(self, arguments):
        self.arguments = arguments
        defines = arguments["--defines"]
        if defines == "off":
            self.defines_file = None
        else:
            self.defines_file = os.path.join(defines)
            if os.path.isdir(self.defines_file):
                self.defines_file = os.path.join(self.defines_file, "defines.yaml")

    def _get_current(self):
        if self.defines_file is None:
            return {}

        try:
            with open(self.defines_file, "rU") as defines_file:
                return yaml.load(defines_file)
        except FileNotFoundError:
            return {}

    current_defines = property(_get_current)

    def set(self, key, value):
        if self.defines_file is None:
            return print("mushformat: defines disabled")

        current_defines = self.current_defines
        current_defines[key] = value

        with open(self.defines_file, "w") as defines_file:
            yaml.dump(current_defines, defines_file, default_flow_style=False)

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
                yaml.dump(current_defines, defines_file, default_flow_style=False)

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
        self.install_directives = {}

        for item in arguments["-D"]:
            if "=" not in item:
                print("mushformat: -D expects KEY=VALUE, got '{}'".format(item))
                sys.exit(1)

            key, value = [x.strip() for x in item.split("=", 1)]
            self.current_defines[key] = value

    def do_directive(self, directive):
        # todo: make this a proper dispatch
        if directive[0].lower() == "define":
            try:
                self.current_defines[directive[1]] = directive[2]
            except IndexError:
                print("Directive '{}' invalid.".format(' '.join(directive)))
                sys.exit(2)
        elif directive[0].lower() == "search":
            if "search" not in self.install_directives:
                self.install_directives["search"] = {}

            self.install_directives["search"][directive[1]] = " ".join(directive[2:])

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

        line = re.sub(r"\s{2,}", self._space_compress, line)

        output.append(line)

        if not line.endswith("\\"):
            output.append("%r")

        return "".join(output)

    def compile(self, source_paths, output_file):
        for source_path in source_paths:
            with io.open(source_path, "rt", encoding="latin1", newline=None) as source_file:
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

                    if "#//" in line:
                        line = line[:line.index("#//")]

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

    def build_project(self, project_path):
        if not os.path.exists(project_path):
            return print("mushformat: project file {} not found".format(project_path))

        with io.open(project_path, 'rt', newline=None) as project_file:
            config = yaml.load(project_file)


        project_root = config.get("root", ".")

        for target_name in config.get("targets", []):

            for target_section in targets:
            target = targets[target_section]

            output_path = target["output"]
            source_files = target["files"]

    def main(self):
        source_paths = self.arguments["SOURCE"]
        output_path = self.arguments["-O"]
        match_pattern = self.arguments["--match"]
        clipboard = self.arguments["--clipboard"]
        project = self.arguments["-P"]
        memory_output = self.arguments.get("--memory")

        if project:
            return self.build_project(project)

        if not source_paths:
            source_paths = filedialog.askopenfilenames(title="Select MUSH Source files?")
            if not source_paths:
                return

        if not output_path and not clipboard and not memory_output:
            output_path = filedialog.asksaveasfilename(title="Save compiled MUSHCode to?")
            if not output_path:
                return

        expanded_paths = []
        for source_path in source_paths:
            source_path = os.path.abspath(source_path)

            expanded_paths.extend(glob.glob(source_path))

        output_path = os.path.abspath(output_path)

        compiled_data = io.StringIO()

        self.compile(expanded_paths, compiled_data)

        compiled_data.seek(0)

        if match_pattern:
            output_data = io.StringIO()
            for line in compiled_data:
                if re.match(match_pattern, line):
                    output_data.write(line)
        else:
            output_data = compiled_data

        output_data.seek(0)
        if clipboard:
            data = output_data.read()
            pyperclip.copy(data.replace("\n", os.linesep))
        else:
            if memory_output:
                return output_data
            else:
                with io.open(output_path, 'wt', newline=None, encoding="latin1") as output_file:
                    output_file.write(output_data.read())

class InstallHandler:
    def __init__(self, arguments):
        self.arguments = arguments

        self.define_handler = DefineHandler(arguments)
        self.current_defines = self.define_handler.current_defines
        self.install_directives = {}

        for item in arguments["-D"]:
            if "=" not in item:
                print("mushformat: -D expects KEY=VALUE, got '{}'".format(item))
                sys.exit(1)

            key, value = [x.strip() for x in item.split("=", 1)]
            self.current_defines[key] = value

    def prepare_source(self):
        arguments = self.arguments.copy()
        arguments["SOURCE"] = arguments["-S"]
        arguments["--memory"] = True

        compile_handler = CompileHandler(arguments)
        output_file = compile_handler.main()

        self.install_directives = compile_handler.install_directives

        return output_file.read()

    def prepare_output(self):
        output_paths = [os.path.abspath(p) for p in self.arguments["-O"]]

        output_data = io.StringIO()

        for output_path in output_paths:
            with io.open(output_path, "rt", encoding="latin1", newline=None) as output_file:
                output_data.write(output_file.read())
                output_data.write("\n\n")

        output_data.seek(0)
        return output_data.read()

    def prepare_project(self):
        project_file = self.arguments["-P"]
        if not os.path.exists(self.arguments["-P"]):
            print("mushformat: can not find project '{}'".format(project_file))
            sys.exit(8)

        project_config = configparser.ConfigParser()
        project_config


    prepare = {
        "source": prepare_source,
        "output": prepare_output,
        "project": prepare_project}

    def main(self):
        if self.arguments["-S"]:
            install_from = "source"
        elif self.arguments["-C"]:
            install_from = "compiled"
        elif self.arguments["-P"]:
            install_from = "project"
        else:
            return print("mushformat: one of -S, -C or -P must be provided")

        if not self.arguments["-H"]:
            return print("mushformat: -H HOSTINI is required")

        host_config = configparser.ConfigParser()
        host_config.read([self.arguments["-H"]])

        try:
            address = host_config["host"]["address"].encode("latin1")
        except KeyError:
            return print("mushformat: HOSTINI requires [host] address= option")

        try:
            port = int(host_config["host"]["port"])
        except KeyError:
            return print("mushformat: HOSTINI requires [host] port= option")
        except ValueError:
            return print("mushformat: HOSTINI requires [host] port= option to be an integer")

        try:
            username = host_config["host"]["username"].encode("latin1")
        except KeyError:
            return print("mushformat: HOSTINI requires [host] username= option")

        try:
            password = host_config["host"]["password"].encode("latin1")
        except KeyError:
            return print("mushformat: HOSTINI requires [host] password= option")

        data = self.prepare[install_from](self)

        self.install(data, address, port, username, password)

    def _get_token(self, __alphanum = string.ascii_letters + string.digits):
        return ''.join(random.sample(__alphanum, 12))

    def _discard_input(self, client):
        time.sleep(1)

        client.read_very_eager()

    def _expect(self, client, seeking, error):
        time.sleep(1)

        text = ""
        while not text:
            text = client.read_very_eager()

        if seeking not in text:
            print("mushformat: {}".format(error))
            sys.exit(6)

    def _get_answer(self, client, token):
        time.sleep(1)

        text = ""
        while not text:
            text = client.read_very_eager()

        if token not in text:
            print("mushformat: install attempted to get answer from MUSH and failed.")
            sys.exit(4)

        try:
            return text[text.index(token)+len(token)+1:text.rindex(token)-1].decode("latin1")
        except ValueError:
            return ''

    def _directive_search(self, client, options, data):
        for define, name in options.items():
            token = self._get_token()

            if define not in self.current_defines:
                client.write("think {} [searchng(%# objects={})] {}\n".format(token, name, token).encode("latin1"))

                answer = self._get_answer(client, token)
                if not answer:
                    print("mushformat: could not find '{}' on server to specify define '{}'.".format(name, define))
                    sys.exit(7)

                print("mushformat: answer to search {!r} = {!r} is: {!r}".format(define, name, answer))
                self.current_defines[define] = answer.strip()
                data = data.replace(define, answer)

        return data

    def _do_install_directives(self, client, data):
        for directive, options in self.install_directives.items():
            if not hasattr(self, '_directive_{}'.format(directive)):
                print("mushformat: install directive {} unknown".format(directive.upper()))
                sys.exit(3)

            data = getattr(self, "_directive_{}".format(directive))(client, options, data)

        return data

    def install(self, data, host, port, username, password):
        client = telnetlib.Telnet(host, port)
        self._discard_input(client)

        client.write(b" ".join((b"connect ", username, password, b"\n")))
        self._discard_input(client)
        client.write(b"@set me=!verbose !puppet !trace\n")
        self._discard_input(client)

        client.write(b"@version\n")
        self._expect(client, b"RhostMUSH", "Installation is only supported on RhostMUSH currently.")

        data = self._do_install_directives(client, data)

        self._discard_input(client)

        print("mushformat: installing...")

        for n, line in enumerate(data.splitlines()):
            print("mushformat:     line #{}".format(n+1))
            client.write((line + "\n").encode("latin1"))
            self._discard_input(client)

        print("mushformat: installation complete.")

def main():
    # if sys.executable.endswith("mushformat.exe") and not sys.argv[1:]:
    #     sys.argv = [sys.argv[0], "compile"]

    arguments = docopt(__doc__, version="mushformat {}".format(__VERSION__))
    handler = None

    root = Tk()
    root.withdraw()

    print("Arguments: {!r}".format(arguments))

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