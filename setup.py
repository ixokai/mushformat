from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need
# fine tuning.
buildOptions = dict(packages = [], excludes = [],
                    include_msvcr=True, append_script_to_exe=True,
                    create_shared_zip=True, icon="icon/windows.ico")

import sys
base = 'Win32GUI' if sys.platform=='win32' else None

default_options = {
    "appendScriptToExe": True,
    "appendScriptToLibrary": False,

}

executables = [
    Executable('mushformat.py', base=base, targetName="mushformat.exe"),
    Executable('mushformat.py', base=None, targetName="mushformat.com")
]

setup(name='mushformat',
      version = '0.1',
      description = 'MUSH Code (Un)Formatter',
      options = dict(build_exe = buildOptions, ),
      executables = executables)
