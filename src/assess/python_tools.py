import os
import os.path as osp
import re
import subprocess
import glob
import logging

from .helper import BuildArtifactsHelper
from .swa_tool import SwaTool


class PythonTool(SwaTool):

    def __init__(self, input_root_dir, build_summary_file, tool_root_dir):
        self._set_python_home(build_summary_file)
        self._set_user_site_packages()
        SwaTool.__init__(self, input_root_dir, tool_root_dir)
        self._get_pkg_lib(build_summary_file)

    def _set_python_home(self, build_summary_file):
        build_artifact_helper = BuildArtifactsHelper(build_summary_file)
        pkg_lang = build_artifact_helper['package-language']
        
        regex = re.compile('[pP]ython-(?P<version>[23])')
        match = regex.search(pkg_lang)
        if match:
            self.python_lang_version = int(match.group('version'))
            if self.python_lang_version == 3:
                self.python_home = osp.expandvars('${SWAMP_PYTHON3_HOME}')
            else:
                self.python_home = osp.expandvars('${SWAMP_PYTHON2_HOME}')

            self.python_exe = '{0}/bin/python{1}'.format(self.python_home,
                                                         self.python_lang_version)

    def _set_user_site_packages(self):
        version = subprocess.check_output([self.python_exe,
                                           '--version'],
                                          stderr=subprocess.STDOUT).decode(encoding='utf-8').strip()
        logging.info('PYTHON VERSION %s', version)
        
        match = re.compile(r'Python\s*(?P<major_version>\d[.]\d)[.]\d').match(version)
        if match:
            major_version = match.group('major_version')
            self.user_site_packages = osp.expandvars('$HOME/.local/lib/python{0}/site-packages'.format(major_version))
            self.user_local_bin = osp.expandvars('$HOME/.local/bin')

    def _get_pkg_lib(self, build_summary_file):
        '''For setuptools and distutils package, <pkg-build-dir>/build/lib*'''

        build_artifact_helper = BuildArtifactsHelper(build_summary_file)
        pkg_dir = build_artifact_helper.get_pkg_dir()
        build_dir = build_artifact_helper['build-dir']
        if build_dir:
            pkg_build_dir = osp.normpath(osp.join(pkg_dir, build_dir))
        else:
            pkg_build_dir = osp.normpath(pkg_dir)

        pkg_lib = glob.glob(osp.join(pkg_build_dir, 'build/lib*'))

        if pkg_lib:
            self.pkg_lib = ':'.join(pkg_lib)
        else:
            self.pkg_lib = None

    def _get_env(self):
        new_env = super()._get_env()
        new_env['PATH'] = '{0}/bin:{1}'.format(self.python_home, new_env['PATH'])
        if hasattr(self, 'user_local_bin') and self.user_local_bin:
            new_env['PATH'] = '{0}:{1}'.format(self.user_local_bin, new_env['PATH'])
        if hasattr(self, 'user_site_packages') and self.user_site_packages:
            new_env['PYTHONPATH'] = self.user_site_packages
        if hasattr(self, 'pkg_lib') and self.pkg_lib:
            new_env['PYTHONPATH'] = '{0}:{1}'.format(new_env['PYTHONPATH'],
                                                     self.pkg_lib)
        return new_env


class Flake8(PythonTool):

    def _set_tool_config(self, pkg_dir):

        self._tool_conf['tool-config-file'] = self._tool_conf['tool-default-config-file']

        # This version has an issue where 'user configuration' file passed as
        # option to command line is given less priority over 'package configuration'
        # (.flake8, setup.cfg, or tox.ini) that if already presting in the package directory

        if self._tool_conf['tool-version'] == '2.4.1':
            for filename in ['.flake8', 'setup.cfg', 'tox.ini']:
                local_config_file = osp.join(pkg_dir, filename)
                if osp.isfile(local_config_file):
                    os.rename(filename, '{0}-original'.format(filename))
