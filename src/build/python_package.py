import os
import os.path as osp
import logging
import glob

from . import common
from .package import Package
from .build_summary import BuildSummary

from .. import utillib
from .. import confreader
from ..logger import LogTaskStatus


class PythonPkg(Package):

    VENV_DIR = 'venv'
    VENV_BIN_DIR = osp.join(VENV_DIR, 'bin')
    
    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        Package.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)
        self._create_venv(input_root_dir, build_root_dir)

    def _get_env(self, pwd):
        new_env = super()._get_env(pwd)
        new_env['PATH'] = '%s:%s' % (self.venv_dir, new_env['PATH'])
        return new_env

    def _get_tool_lang(self, input_root_dir):

        run_conf = confreader.read_conf_into_dict(osp.join(input_root_dir, 'run.conf'))
        if 'assess' not in run_conf['goal']:
            return 3
        else:
            tool_conf = confreader.read_conf_into_dict(osp.join(input_root_dir, 'tool.conf'))
            return int(tool_conf['python-flavor']) if 'python-flavor' in tool_conf else 3
    
    def _create_venv(self, input_root_dir, build_root_dir):
        pkg_lang = self.pkg_conf['package-language'].lower()

        if 'python-2 python-3' in pkg_lang:
            self.python_lang_version = self._get_tool_lang(input_root_dir)

            # Changing the language in case if it is 'Python-2 Python-3' to self.python_lang_version
            self.pkg_conf['package-language'] = pkg_lang.replace('python-2 python-3',
                                                                 'python-{0}'.format(self.python_lang_version))
                    
        elif 'python-2' in pkg_lang:
            self.python_lang_version = 2
        elif 'python-3' in pkg_lang:
            self.python_lang_version = 3
        else:
            self.python_lang_version = self._get_tool_lang(input_root_dir)

        logging.info('PYTHON LANGUAGE VERSION: %s' % self.python_lang_version)
        logging.info('PACKAGE LANGUAGE: %s' % pkg_lang)
        
        if self.python_lang_version == 3:
            venv_cmd = osp.expandvars('${SWAMP_PYTHON3_HOME}/bin/pyvenv venv')
        else:
            venv_cmd = osp.expandvars('${SWAMP_PYTHON2_HOME}/bin/virtualenv venv')

        exit_code, _ = utillib.run_cmd(venv_cmd, cwd=build_root_dir, description='CREATE VENV')
        self.venv_dir = osp.join(build_root_dir, PythonPkg.VENV_BIN_DIR)
    
    def _install_pkg_dependencies(self, build_root_dir, build_summary):

        with LogTaskStatus('install-pkg-dependencies', msg_inline='pip') as lts:

            if 'package-pip-install-file' not in self.pkg_conf:
                lts.skip_task()
            else:
                pip_cmd = 'pip install -r {0} {1}'.format(osp.join(self.pkg_dir,
                                                                   self.pkg_conf['package-pip-install-file']),
                                                          self.pkg_conf.get('package-pip-install-opt', ''))

                outfile = osp.join(build_root_dir, 'pip_install.out')
                errfile = osp.join(build_root_dir, 'pip_install.err')

                exit_code, environ = utillib.run_cmd(pip_cmd,
                                                     cwd=self.pkg_dir,
                                                     outfile=outfile,
                                                     errfile=errfile,
                                                     env=self._get_env(self.pkg_dir),
                                                     description='PIP INSTALL')

                build_summary.add_command('pip-install', pip_cmd,
                                          [], exit_code, environ,
                                          environ['PWD'],
                                          outfile, errfile)

                if exit_code != 0:
                    build_summary.add_exit_code(exit_code)
                    raise common.CommandFailedError(pip_cmd, exit_code,
                                                    BuildSummary.FILENAME,
                                                    osp.relpath(outfile, build_root_dir),
                                                    osp.relpath(errfile, build_root_dir))

    def build(self, build_root_dir):

        with BuildSummary(build_root_dir,
                          common.PKG_ROOT_DIRNAME,
                          self.pkg_conf) as build_summary:

            self._configure(build_root_dir, build_summary)
            self._install_pkg_dependencies(build_root_dir, build_summary)
            return self._build(build_root_dir, build_summary)


class PythonDistUtilsPkg(PythonPkg):

    def get_build_cmd(self):
        build_cmd = 'python'
        build_cmd += ' ' + self.pkg_conf.get('build-file', 'setup.py')
        build_cmd += ' ' + self.pkg_conf.get('build-target', 'build')
        build_cmd += ' ' + self.pkg_conf.get('build-opt', '')
        return build_cmd

    def get_main_dir(self, pkg_build_dir):
        return glob.glob(osp.join(pkg_build_dir, 'build/lib*'))

    
class PythonWheelPkg(PythonPkg):

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        ''' Do not call Package.__init__'''
        
        self.pkg_conf = confreader.read_conf_into_dict(pkg_conf_file)
        self.pkg_conf['package-language'] = self.pkg_conf['package-language'].lower()
        self.input_root_dir = input_root_dir
        
        with LogTaskStatus('package-unarchive') as lts:
            # pkg_archive = osp.join(input_root_dir, self.pkg_conf['package-archive'])
            pkg_root_dir = osp.join(build_root_dir, common.PKG_ROOT_DIRNAME)
            pkg_dir = osp.normpath(osp.join(pkg_root_dir, self.pkg_conf['package-dir']))

            if not osp.isdir(pkg_dir):
                os.makedirs(pkg_dir)

            self.pkg_dir = pkg_dir
            lts.skip_task()

        self._create_venv(input_root_dir, build_root_dir)
        # TODO: This must be part of python installation
        # This must go away
        utillib.run_cmd('pip install wheel',
                        env=self._get_env(self.pkg_dir),
                        description='INSTALL PYTHON WHEEL')
        
    def get_build_cmd(self):
        pkg_archive = osp.join(self.input_root_dir, self.pkg_conf['package-archive'])
        return 'pip install {0} && wheel unpack --dest {1} {0}'.format(pkg_archive, self.pkg_dir)


class PythonOtherPkg(PythonPkg):

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        PythonPkg.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

    def get_build_cmd(self):
        return '{0} {1} {2} {3}'.format(self.pkg_conf.get('build-cmd', ''),
                                        self.pkg_conf.get('build-file', ''),
                                        self.pkg_conf.get('build-opt', ''),
                                        self.pkg_conf.get('build-target', ''))


class PythonNoBuildPkg(PythonPkg):
    ''' Nobuild sure that 'install pip dependencies' is called '''

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        PythonPkg.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

    def get_build_cmd(self):
        ''' Returns dummy build command'''
        return ':'

