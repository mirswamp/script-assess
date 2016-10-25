import os
import os.path as osp
import logging
import glob

from .common import PKG_ROOT_DIRNAME
from .package import Package
from .build_summary import BuildSummary
from .common import CommandFailedError

from .. import utillib
from ..utillib import NotADirectoryException
from ..logger import LogTaskStatus


class PythonPkg(Package):

    VENV_SUB_DIR = 'venv/bin'
    
    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        Package.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

        self._create_venv(input_root_dir, build_root_dir)

    def _get_env(self):
        new_env = dict(os.environ)
        new_env['PATH'] = '%s:%s' % (self.venv_dir, new_env['PATH'])
        return new_env
    
    def _create_venv(self, input_root_dir, build_root_dir):
        python_lang = self.pkg_conf['package-language'].lower()

        if python_lang == 'python-2 python-3':
            self.python_lang_version = 3
        else:
            self.python_lang_version = int(python_lang[-1])
            
        logging.info('Python language version %s' % self.python_lang_version)

        if self.python_lang_version == 3:
            venv_cmd = osp.expandvars('${SWAMP_PYTHON3_HOME}/bin/pyvenv venv')
        else:
            venv_cmd = osp.expandvars('${SWAMP_PYTHON2_HOME}/bin/virtualenv venv')

        exit_code, _ = utillib.run_cmd(venv_cmd, cwd=build_root_dir, description='CREATE VENV')
        self.venv_dir = osp.join(build_root_dir, PythonPkg.VENV_SUB_DIR)

        # pip_upgrade_cmd = 'pip install --upgrade pip'
        
        # if self.python_lang_version == 3:
        #     # install wheel
        #     pip_upgrade_cmd = pip_upgrade_cmd + ' && pip install wheel'
            
        # utillib.run_cmd(pip_upgrade_cmd,
        #                 cwd=build_root_dir,
        #                 env=self._get_env(),
        #                 description='CREATE VENV')

    def get_build_cmd(self):

        if self.pkg_conf['build-sys'] in ['python-distutils', 'python-setuptools']:
            build_cmd = 'python'
            build_cmd += ' ' + self.pkg_conf.get('build-file', 'setup.py')
            build_cmd += ' ' + self.pkg_conf.get('build-target', 'build')
            build_cmd += ' ' + self.pkg_conf.get('build-opt', '')
            return build_cmd
        
    def build(self, build_root_dir):

        with BuildSummary(build_root_dir,
                          PKG_ROOT_DIRNAME,
                          self.pkg_conf) as build_summary:

            self._configure(build_root_dir, build_summary)

            with LogTaskStatus('build'):

                pkg_build_dir = osp.normpath(osp.join(self.pkg_dir,
                                                      self.pkg_conf.get('build-dir', '.')))

                if not osp.isdir(pkg_build_dir):
                    LogTaskStatus.log_task('chdir-build-dir', 1, None,
                                           "Directory '{0}' not found".format(osp.basename(pkg_build_dir)))
                    raise NotADirectoryException()

                build_cmd = self.get_build_cmd()
                outfile = osp.join(build_root_dir, 'build_stdout.out')
                errfile = osp.join(build_root_dir, 'build_stderr.err')

                exit_code, environ = utillib.run_cmd(build_cmd,
                                                     cwd=pkg_build_dir,
                                                     env=self._get_env(),
                                                     description='BUILD')
                
                build_summary.add_command('build', build_cmd,
                                          [], exit_code, environ,
                                          environ['PWD'],
                                          outfile, errfile)

                if exit_code != 0:
                    build_summary.add_exit_code(exit_code)
                    raise CommandFailedError(build_cmd, exit_code,
                                             BuildSummary.FILENAME,
                                             osp.relpath(outfile, build_root_dir),
                                             osp.relpath(errfile, build_root_dir))

                fileset = set()
                for pattern in glob.glob(osp.join(pkg_build_dir, 'build/lib*')):
                    fileset.update(self.get_src_files(pattern,
                                                      self.pkg_conf.get('package-exclude-paths', '')))

                build_summary.add_exit_code(exit_code)
                build_summary.add_build_artifacts(fileset)
                return (exit_code, BuildSummary.FILENAME)

                    
