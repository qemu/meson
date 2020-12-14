# Copyright 2020 The Meson development team

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pathlib
import pickle
import re
import os
import sys
import typing as T

from ..backend.ninjabackend import TargetDependencyScannerInfo
from ..compilers.compilers import lang_suffixes

cpp_import_re = re.compile('\w*import ([a-zA-Z0-9]+);')
cpp_export_re = re.compile('\w*export module ([a-zA-Z0-9]+);')

FORTRAN_INCLUDE_PAT = r"^\s*#?include\s*['\"](\w+\.\w+)['\"]"
FORTRAN_MODULE_PAT = r"^\s*\bmodule\b\s+(\w+)\s*(?:!+.*)*$"
FORTRAN_SUBMOD_PAT = r"^\s*\bsubmodule\b\s*\((\w+:?\w+)\)\s*(\w+)"
FORTRAN_USE_PAT = r"^\s*use,?\s*(?:non_intrinsic)?\s*(?:::)?\s*(\w+)"

fortran_module_re = re.compile(FORTRAN_MODULE_PAT)
fortran_use_re = re.compile(FORTRAN_USE_PAT)

class DependencyScanner:
    def __init__(self, pickle_file: str, outfile: str, sources: T.List[str]):
        with open(pickle_file, 'rb') as pf:
            self.target_data = pickle.load(pf) # type: TargetDependencyScannerInfo
        self.outfile = outfile
        self.sources = sources
        self.provided_by = {} # type: T.Dict[str, str]
        self.exports = {} # type: T.Dict[str, str]
        self.needs = {} # type: T.Dict[str, T.List[str]]
        self.sources_with_exports = [] # type: T.List[str]
    
    def scan_file(self, fname: str) -> None:
        suffix = os.path.splitext(fname)[1][1:]
        if suffix in lang_suffixes['fortran']:
            self.scan_fortran_file(fname)
        elif suffix in lang_suffixes['cpp']:
            self.scan_fortran_file(fname)
        else:
            sys.exit('Can not scan files with suffix .{}.'.format(suffix))

    def scan_fortran_file(self, fname: str) -> None:
        fpath = pathlib.Path(fname)
        for line in fpath.read_text().split('\n'):
            import_match = fortran_use_re.match(line)
            export_match = fortran_module_re.match(line)
            if import_match:
                needed = import_match.group(1)
                if fname in self.needs:
                    self.needs[fname].append(needed)
                else:
                    self.needs[fname] = [needed]
            if export_match:
                exported_module = export_match.group(1)
                if exported_module in self.provided_by:
                    raise RuntimeError('Multiple files provide module {}.'.format(exported_module))
                self.sources_with_exports.append(fname)
                self.provided_by[exported_module] = fname
                self.exports[fname] = exported_module

    def scan_cpp_file(self, fname: str) -> None:
        fpath = pathlib.Path(fname)
        for line in fpath.read_text().split('\n'):
            import_match = cpp_import_re.match(line)
            export_match = cpp_export_re.match(line)
            if import_match:
                needed = import_match.group(1)
                if fname in self.needs:
                    self.needs[fname].append(needed)
                else:
                    self.needs[fname] = [needed]
            if export_match:
                exported_module = export_match.group(1)
                if exported_module in self.provided_by:
                    raise RuntimeError('Multiple files provide module {}.'.format(exported_module))
                self.sources_with_exports.append(fname)
                self.provided_by[exported_module] = fname
                self.exports[fname] = exported_module
    def objname_for(self, src: str) -> str:
        objname = self.target_data.source2object[src]
        assert(isinstance(objname, str))
        return objname

    def module_name_for(self, src: str) -> str:
        suffix= os.path.splitext(src)[1][1:]
        if suffix in lang_suffixes['fortran']:
            return os.path.join(self.target_data.private_dir, '{}.mod'.format(self.exports[src]))
        elif suffix in lang_suffixes['cpp']:
            return '{}.ifc'.format(self.exports[src])
        else:
            raise RuntimeError('Unreachable code.')

    def scan(self) -> int:
        for s in self.sources:
            self.scan_file(s)
        with open(self.outfile, 'w') as ofile:
            ofile.write('ninja_dyndep_version = 1\n')
            for src in self.sources:
                objfilename = self.objname_for(src)
                if src in self.sources_with_exports:
                    ifc_entry = '| ' + self.module_name_for(src)
                else:
                    ifc_entry = ''
                if src in self.needs:
                    # FIXME, handle all sources, not just the first one
                    modname = self.needs[src][0]
                    provider_src = self.provided_by[modname]
                    provider_modfile = self.module_name_for(provider_src)
                    mod_dep = '| ' + provider_modfile
                else:
                    mod_dep = ''
                ofile.write('build {} {}: dyndep {}\n'.format(objfilename,
                                                              ifc_entry,
                                                              mod_dep))
        return 0

def run(args: T.List[str]) -> int:
    pickle_file = args[0]
    outfile = args[1]
    sources = args[2:]
    scanner = DependencyScanner(pickle_file, outfile, sources)
    return scanner.scan()
