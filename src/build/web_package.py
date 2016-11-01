import os.path as osp
import json

from .common import PKG_ROOT_DIRNAME
from .package import Package
from .build_summary import BuildSummary
from .common import CommandFailedError

from .. import utillib
from ..utillib import NotADirectoryException
from ..logger import LogTaskStatus


class JsNodePkg(Package):

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        Package.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

    def get_nodejs_files(self, pkg_dir):

        def npm_ignore_list():
            ignore_file = None

            if osp.isfile(osp.join(pkg_dir, '.npmignore')):
                ignore_file = osp.join(pkg_dir, '.npmignore')
            elif osp.isfile(osp.join(pkg_dir, '.gitignore')):
                ignore_file = osp.join(pkg_dir, '.gitignore')

            if ignore_file:
                with open(ignore_file) as fobj:
                    ignore_patterns = {p.strip().strip('\n') for p in fobj
                                       if p and not p.isspace() and not p.strip().startswith('#')}
                    ignore_patterns.add('node_modules')
                    return ignore_patterns

        fileset = set()

        with open(osp.join(pkg_dir, 'package.json')) as fobj:
            pkg_json = json.load(fobj)

            if 'main' in pkg_json:
                if osp.isfile(osp.join(pkg_dir, pkg_json['main'])):
                    fileset.add(osp.join(pkg_dir, pkg_json['main']))

            if 'files' in pkg_json:
                for _file in [osp.join(pkg_dir, f)
                              for f in pkg_json['files']]:
                    if osp.isdir(_file):
                        fileset.update(utillib.get_file_list(_file, None,
                                                             Package.get_file_types(self.pkg_conf['package-language'])))
                    else:
                        fileset.add(_file)
            else:
                fileset.update(utillib.get_file_list(pkg_dir,
                                                     npm_ignore_list(),
                                                     Package.get_file_types(self.pkg_conf['package-language'])))

        return fileset

    def is_a_node_pkg(self, pkg_dir):
        return True if (self.pkg_conf['build-sys'] == 'npm' and
                        osp.isfile(osp.join(pkg_dir, 'package.json'))) else False

    def get_src_files(self, pkg_dir, exclude_filter):

        file_filters = utillib.get_file_filters(pkg_dir, exclude_filter.split(','))

        fileset = set()
        if self.is_a_node_pkg(pkg_dir):
            fileset = self.get_nodejs_files(pkg_dir)
        else:
            fileset.update(utillib.get_file_list(pkg_dir,
                                                 None,
                                                 Package.get_file_types(self.pkg_conf['package-language'])))

        fileset = fileset.difference(file_filters.exclude_files)

        fileset = fileset.difference(_file for _file in fileset
                                     for exdir in file_filters.exclude_dirs
                                     if _file.startswith(osp.join(exdir, '')))

        return fileset

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

                if self.pkg_conf['build-sys'] == 'npm':
                    build_cmd = 'npm install'
                elif self.pkg_conf['build-sys'] == 'composer':
                    build_cmd = 'php ${VMINPUTDIR}/composer.phar install --no-interaction --no-progress'
                elif self.pkg_conf['build-sys'] == 'pear':
                    build_cmd = 'pear config-set php_dir ${BUILD_DIR}/user_lib && pear install --alldeps --register-only ${VMINPUTDIR}/%s' % self.pkg_conf['package-archive']
                else:
                    build_cmd = ':'

                outfile = osp.join(build_root_dir, 'build_stdout.out')
                errfile = osp.join(build_root_dir, 'build_stderr.err')

                exit_code, environ = utillib.run_cmd(build_cmd,
                                                     outfile,
                                                     errfile,
                                                     cwd=pkg_build_dir,
                                                     env=Package.get_env(pkg_build_dir),
                                                     description="BUILD")

                build_summary.add_command('build', build_cmd,
                                          [], exit_code, environ,
                                          environ['PWD'],
                                          outfile, errfile)

                build_summary.add_exit_code(exit_code)

                if exit_code != 0:
                    raise CommandFailedError(build_cmd, exit_code,
                                             BuildSummary.FILENAME,
                                             osp.relpath(outfile, build_root_dir),
                                             osp.relpath(errfile, build_root_dir))

                fileset = self.get_src_files(pkg_build_dir,
                                             self.pkg_conf.get('package-exclude-paths', ''))

                build_summary.add_build_artifacts(fileset, self.pkg_conf['package-language'])
                return (exit_code, BuildSummary.FILENAME)

