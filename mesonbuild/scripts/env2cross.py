#!/usr/bin/env python3

# Copyright 2017 Jussi Pakkanen

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys, os, subprocess, shutil

import argparse

def add_arguments(parser: 'argparse.ArgumentParser') -> None:
    parser.add_argument('--debarch', default=None,
                        help='The dpkg architecture to generate.')
    parser.add_argument('--gccsuffix', default="",
                        help='A particular gcc version suffix if necessary.')
    parser.add_argument('-o', required=True, dest='outfile',
                        help='The output file.')

#parser = argparse.ArgumentParser(description='''Generate cross compilation definition file for the Meson build system.
#
#If you do not specify the --arch argument, Meson assumes that running
#plain 'dpkg-architecture' will return correct information for the
#host system.
#
#This script must be run in an environment where CPPFLAGS et al are set to the
#same values used in the actual compilation.
#'''
#)

def locate_path(program):
    if os.path.isabs(program):
        return program
    for d in os.get_exec_path():
        f = os.path.join(d, program)
        if os.access(f, os.X_OK):
            return f
    raise ValueError("%s not found on $PATH" % program)

def write_args_line(ofile, name, args):
    if len(args) == 0:
        return
    ostr = name + ' = ['
    ostr += ', '.join("'" + i + "'" for i in args)
    ostr += ']\n'
    ofile.write(ostr)

def write_args_from_envvars(ofile):
    import shlex
    cppflags = shlex.split(os.environ.get('CPPFLAGS', ''))
    cflags = shlex.split(os.environ.get('CFLAGS', ''))
    cxxflags = shlex.split(os.environ.get('CXXFLAGS', ''))
    ldflags = shlex.split(os.environ.get('LDFLAGS', ''))

    c_args = cppflags + cflags
    cpp_args = cppflags + cxxflags
    c_link_args = cflags + ldflags
    cpp_link_args = cxxflags + ldflags

    write_args_line(ofile, 'c_args', c_args)
    write_args_line(ofile, 'cpp_args', cpp_args)
    write_args_line(ofile, 'c_link_args', c_link_args)
    write_args_line(ofile, 'cpp_link_args', cpp_link_args)

cpu_family_map = dict(mips64el="mips64",
                      i686='x86')
cpu_map = dict(armhf="arm7hlf",
               mips64el="mips64",)

class CrossInfo:
    def __init__(self):
        self.compilers = {}
        self.binaries = {}
        self.properties = {}
        
        self.system = None
        self.cpu = None
        self.cpu_family = None
        self.endian = None

def deb_compiler_lookup(infos, compilerstems, host_arch, gccsuffix):
    for langname, stem in compilerstems:
        compilername = f'{host_arch}-{stem}{gccsuffix}'
        try:
            p = locate_path(compilername)
            infos.compilers[langname] = p
        except ValueError:
            pass

def detect_debianlike(options):
    if options.debarch is None:
        cmd = ['dpkg-architecture']
    else:
        cmd = ['dpkg-architecture', '-a' + options.debarch]
    output = subprocess.check_output(cmd, universal_newlines=True,
                                     stderr=subprocess.DEVNULL)
    data = {}
    for line in output.split('\n'):
        line = line.strip()
        if line == '':
            continue
        k, v = line.split('=', 1)
        data[k] = v
    host_arch = data['DEB_HOST_GNU_TYPE']
    host_os = data['DEB_HOST_ARCH_OS']
    host_cpu_family = cpu_family_map.get(data['DEB_HOST_GNU_CPU'],
                                         data['DEB_HOST_GNU_CPU'])
    host_cpu = cpu_map.get(data['DEB_HOST_ARCH'],
                           data['DEB_HOST_ARCH'])
    host_endian = data['DEB_HOST_ARCH_ENDIAN']
    
    compilerstems = [('c', 'gcc'),
                     ('cpp', 'h++'),
                     ('objc', 'gobjc'),
                     ('objcpp', 'gobjc++')]
    infos = CrossInfo()
    deb_compiler_lookup(infos, compilerstems, host_arch, options.gccsuffix)
    if len(infos.compilers) == 0:
        print('Warning: no compilers were detected.')
    infos.binaries['ar'] = locate_path("%s-ar" % host_arch)
    infos.binaries['strip'] = locate_path("%s-strip" % host_arch)
    infos.binaries['objcopy'] = locate_path("%s-objcopy" % host_arch)
    infos.binaries['ld'] = locate_path("%s-ld" % host_arch)
    try:
        infos.binaries['pkgconfig'] =  locate_path("%s-pkg-config" % host_arch)
    except ValueError:
        pass # pkg-config is optional
    try:
        infos.binaries['cups-config'] = locate_path("cups-config")
    except ValueError:
        pass
    infos.system = host_os
    infos.cpu_family = host_cpu_family
    infos.cpu = host_cpu
    infos.endian = host_endian

    return infos

def write_crossfile(infos, ofilename):
    tmpfilename = ofilename + '~'
    with open(tmpfilename, 'w') as ofile:
        ofile.write('[binaries]\n')
        ofile.write('# Compilers\n')
        for langname in sorted(infos.compilers.keys()):
            compiler = infos.compilers[langname]
            ofile.write(f"{langname} = '{compiler}'\n")
        ofile.write('\n')

        ofile.write('# Other binaries\n')
        for exename in sorted(infos.binaries.keys()):
            exe = infos.binaries[exename]
            ofile.write(f"{exename} = '{exe}'\n")
        ofile.write('\n')
        
        ofile.write('[host_machine]\n')
        ofile.write(f"cpu = '{infos.cpu}'\n")
        ofile.write(f"cpu_family = '{infos.cpu_family}'\n")
        ofile.write(f"endian = '{infos.endian}'\n")
        ofile.write(f"system = '{infos.system}'\n")
    os.replace(tmpfilename, ofilename)

def run(options):
    if options.debarch:
        print('Detecting cross environment via dpkg-reconfigure.')
        infos = detect_debianlike(options)
    else:
        #print('Detecting cross environment via environment variables')
        sys.exit('Can currently only detect debianlike. Patches welcome.')
    write_crossfile(infos, options.outfile)

if __name__ == '__main__':
    options = parser.parse_args()
    run(options)
