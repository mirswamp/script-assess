import os
import os.path as osp
import logging
from abc import ABCMeta

from .common import PKG_ROOT_DIRNAME
from .common import LANG_EXT_MAPPING
from .common import CommandFailedError
from .build_summary import BuildSummary

from .. import utillib
from .. import confreader
from ..logger import LogTaskStatus


from ..utillib import UnpackArchiveError
from ..utillib import NotADirectoryException


#class Package(ABCMeta):
class Package:

    @classmethod
    def get_file_types(cls, pkg_lang):
        '''pkg_lang is a string'''

        ext_list = []
        for lang in pkg_lang.split():
            ext_list.extend(LANG_EXT_MAPPING[lang.lower()])
        return ext_list

    @classmethod
    def get_env(cls, pwd):
        new_env = dict(os.environ)
        if 'PWD' in new_env:
            new_env['PWD'] = pwd

        return new_env

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):

        self.pkg_conf = confreader.read_conf_into_dict(pkg_conf_file)
        self.pkg_conf['package-language'] = self.pkg_conf['package-language'].lower()
        
        with LogTaskStatus('package-unarchive'):
            pkg_archive = osp.join(input_root_dir, self.pkg_conf['package-archive'])
            pkg_root_dir = osp.join(build_root_dir, PKG_ROOT_DIRNAME)
            status = utillib.unpack_archive(pkg_archive, pkg_root_dir, True)

            if status != 0:
                raise UnpackArchiveError(osp.basename(pkg_archive))

            pkg_dir = osp.join(pkg_root_dir, self.pkg_conf['package-dir'])

            if not osp.isdir(pkg_dir):
                LogTaskStatus.log_task('chdir-package-dir', 1, None,
                                       "Directory '{0}' not found".format(osp.basename(pkg_dir)))
                raise NotADirectoryException()

            self.pkg_dir = pkg_dir

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
                                           "Directory '{0}' not found".format(osp.basename(config_dir)))
                    raise NotADirectoryException()

                config_cmd = '%s %s' % (self.pkg_conf['config-cmd'],
                                        self.pkg_conf.get('config-opt', ''))

                outfile = osp.join(build_root_dir, 'config_stdout.out')
                errfile = osp.join(build_root_dir, 'config_stderr.out')

                exit_code, environ = utillib.run_cmd(config_cmd,
                                                     outfile,
                                                     errfile,
                                                     cwd=config_dir,
                                                     env=Package.get_env(config_dir),
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
                    raise CommandFailedError(config_cmd,
                                             exit_code,
                                             BuildSummary.FILENAME,
                                             osp.relpath(outfile, build_root_dir),
                                             osp.relpath(errfile, build_root_dir))

    def build(self, build_root_dir):
        raise NotImplementedError()
