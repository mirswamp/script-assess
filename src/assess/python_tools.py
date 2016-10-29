import os
import os.path as osp
import re
import subprocess

from .helper import BuildArtifactsHelper
from .swa_tool import SwaTool
from ..build.python_package import PythonPkg


class PythonTool(SwaTool):
    
    def __init__(self, input_root_dir, build_summary_file, tool_root_dir):
        self._set_venv_bin(build_summary_file)
        SwaTool.__init__(self, input_root_dir, tool_root_dir)
        self._set_venv_lib(build_summary_file)

    def _set_venv_bin(self, build_summary_file):
        build_artifact_helper = BuildArtifactsHelper(build_summary_file)
        build_root_dir = build_artifact_helper['build-root-dir']
        self.venv_bin = osp.join(build_root_dir, PythonPkg.VENV_BIN_DIR)
        
    def _set_venv_lib(self, build_summary_file):
        build_artifact_helper = BuildArtifactsHelper(build_summary_file)
        build_root_dir = build_artifact_helper['build-root-dir']
        pkg_lang = build_artifact_helper['package-language']

        self.venv_lib = None
        regex = re.compile('Python-(?P<version>[23])')
        m = regex.search(pkg_lang)
        if m:
            python_lang_version = m.group('version')
            if python_lang_version == 2:
                self.venv_lib = '{0}/lib/python2.7/site-packages'.format(osp.join(build_root_dir,
                                                                                  PythonPkg.VENV_DIR))
            else:
                major_version = self._get_python_major_version(python_lang_version)
                if major_version:
                    self.venv_lib = '{0}/lib/python{1}/site-packages'.format(osp.join(build_root_dir,
                                                                                     PythonPkg.VENV_DIR),
                                                                             major_version)

    def _get_python_major_version(self, python_lang_version):
        
        #version = subprocess.check_output(['python', '--version'],
        #                                  self._get_env()).decode(encoding='utf-8').strip()
        regex = re.compile('Python\s*(?P<major_version>\d[.]\d)[.]\d')
        m = regex.match('Python 3.5.2')
        if m:
            return m.group('major_version')
            
    def _get_env(self):
        new_env = super()._get_env()
        new_env['PATH'] = '{0}:{1}'.format(self.venv_bin, new_env['PATH'])
        if self.venv_lib:
            new_env['PYTHONPATH'] = self.venv_lib
        return new_env

    
class Flake8(PythonTool):

    def _set_tool_config(self, pkg_dir):

        # if self._tool_conf.get('tool-config-required', None) == 'true':
        #     if 'tool-config-file' in self._tool_conf and \
        #        osp.isfile(osp.join(pkg_dir, self._tool_conf['tool-config-file'])):
        #         # Make the path absolute
        #         self._tool_conf['tool-config-file'] = osp.normpath(osp.join(pkg_dir,
        #                                                                     self._tool_conf['tool-config-file']))
        #     else:
        #         self._tool_conf['tool-config-file'] = self._tool_conf['tool-default-config-file']

        self._tool_conf['tool-config-file'] = self._tool_conf['tool-default-config-file']

        # This version has an issue where 'user configuration' file passed as
        # option to command line is given less priority over 'package configuration'
        # (.flake8, setup.cfg, or tox.ini) that if already presting in the package directory

        if self._tool_conf['tool-version'] == '2.4.1':
            for filename in ['.flake8', 'setup.cfg', 'tox.ini']:
                local_config_file = os.join(pkg_dir, filename)
                if osp.isfile(local_config_file):
                    os.rename(filename, '{0}-original'.format(filename)

