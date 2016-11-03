import os
import os.path as osp
# from abc import ABCMeta

from . import common
from .build_summary import BuildSummary

from .. import utillib
from .. import fileutil
from .. import confreader
from ..logger import LogTaskStatus

from ..utillib import UnpackArchiveError
from ..utillib import NotADirectoryException


class Package:
    # class Package(ABCMeta):
    ''' TODO: This must be an abstract class '''

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):

        self.pkg_conf = confreader.read_conf_into_dict(pkg_conf_file)
        self.pkg_conf['package-language'] = self.pkg_conf['package-language'].lower()
        self.input_root_dir = input_root_dir

        self._unarchive(build_root_dir)

        pkg_root_dir = osp.join(build_root_dir, common.PKG_ROOT_DIRNAME)
        pkg_dir = osp.join(pkg_root_dir, self.pkg_conf['package-dir'])

        if not osp.isdir(pkg_dir):
            LogTaskStatus.log_task('chdir-package-dir', 1, None,
                                   "Directory '{0}' not found".format(osp.relpath(pkg_dir, pkg_root_dir)))
            raise NotADirectoryException()

        self.pkg_dir = osp.normpath(pkg_dir)
    
    def _get_env(self, pwd):
        new_env = dict(os.environ)
        if 'PWD' in new_env:
            new_env['PWD'] = pwd
        return new_env
    
    def _unarchive(self, build_root_dir):

        with LogTaskStatus('package-unarchive'):
            pkg_archive = osp.join(self.input_root_dir, self.pkg_conf['package-archive'])
            pkg_root_dir = osp.join(build_root_dir, common.PKG_ROOT_DIRNAME)

            if utillib.unpack_archive(pkg_archive, pkg_root_dir, True) != 0:
                raise UnpackArchiveError(osp.basename(pkg_archive))
        
    def _configure(self, build_root_dir, build_summary):

        with LogTaskStatus('configure') as status_dot_out:

            if 'config-cmd' not in self.pkg_conf \
               or len(self.pkg_conf['config-cmd'].strip()) == 0:
                status_dot_out.skip_task()
            else:
                config_dir = osp.normpath(osp.join(self.pkg_dir,
                                                   self.pkg_conf.get('config-dir', '.')))

                if not osp.isdir(config_dir):
                    LogTaskStatus.log_task('chdir-config-dir', 1, None,
                                           "Directory '{0}' not found".format(osp.relpath(config_dir,
                                                                                          self.pkg_dir)))
                    raise NotADirectoryException()

                config_cmd = '%s %s' % (self.pkg_conf['config-cmd'],
                                        self.pkg_conf.get('config-opt', ''))

                outfile = osp.join(build_root_dir, 'config.out')
                errfile = osp.join(build_root_dir, 'config.out')

                exit_code, environ = utillib.run_cmd(config_cmd,
                                                     outfile,
                                                     errfile,
                                                     cwd=config_dir,
                                                     env=self._get_env(config_dir),
                                                     description="CONFIGURE")

                build_summary.add_command('configure',
                                          config_cmd,
                                          [],
                                          exit_code,
                                          environ,
                                          config_dir,
                                          outfile,
                                          errfile)

                if exit_code != 0:
                    build_summary.add_exit_code(exit_code)
                    raise common.CommandFailedError(config_cmd,
                                                    exit_code,
                                                    BuildSummary.FILENAME,
                                                    osp.relpath(outfile, build_root_dir),
                                                    osp.relpath(errfile, build_root_dir))

    def get_build_cmd(self):
        raise NotImplementedError('Cannot use this class directly')

    def get_main_dir(self, pkg_build_dir):
        yield pkg_build_dir

    def _build(self, build_root_dir, build_summary):

        with LogTaskStatus('build'):

            pkg_build_dir = osp.normpath(osp.join(self.pkg_dir,
                                                  self.pkg_conf.get('build-dir', '.')))

            if not osp.isdir(pkg_build_dir):
                LogTaskStatus.log_task('chdir-build-dir', 1, None,
                                       "Directory '{0}' not found".format(osp.relpath(pkg_build_dir,
                                                                                      self.pkg_dir)))
                raise NotADirectoryException()

            build_cmd = self.get_build_cmd()
            outfile = osp.join(build_root_dir, 'build.out')
            errfile = osp.join(build_root_dir, 'build.err')

            exit_code, environ = utillib.run_cmd(build_cmd,
                                                 cwd=pkg_build_dir,
                                                 outfile=outfile,
                                                 errfile=errfile,
                                                 env=self._get_env(pkg_build_dir),
                                                 description='BUILD')

            build_summary.add_command('build', build_cmd,
                                      [], exit_code, environ,
                                      environ['PWD'],
                                      outfile, errfile)

            build_summary.add_exit_code(exit_code)

            if exit_code != 0:
                raise common.CommandFailedError(build_cmd, exit_code,
                                                BuildSummary.FILENAME,
                                                osp.relpath(outfile, build_root_dir),
                                                osp.relpath(errfile, build_root_dir))

            fileset = set()
            for dir_path in self.get_main_dir(pkg_build_dir):
                fileset.update(self.get_src_files(dir_path,
                                                  self.pkg_conf.get('package-exclude-paths',
                                                                    '')))

            build_summary.add_build_artifacts(fileset, self.pkg_conf['package-language'])
            return (exit_code, BuildSummary.FILENAME)
                
    def get_src_files(self, pkg_dir, exclude_filter):

        fileset = set()
        fileset.update(fileutil.get_file_list(pkg_dir, None,
                                              common.get_file_extentions(self.pkg_conf['package-language'])))
        
        file_filters = fileutil.get_file_filters(pkg_dir, exclude_filter.split(','))
        fileset = fileset.difference(file_filters.exclude_files)
        fileset = fileset.difference(_file for _file in fileset
                                     for exdir in file_filters.exclude_dirs
                                     if _file.startswith(osp.join(exdir, '')))
        return fileset
    
    def build(self, build_root_dir):

        with BuildSummary(build_root_dir,
                          common.PKG_ROOT_DIRNAME,
                          self.pkg_conf) as build_summary:

            self._configure(build_root_dir, build_summary)
            return self._build(build_root_dir, build_summary)

