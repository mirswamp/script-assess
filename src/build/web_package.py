import os.path as osp
import json

from . import common
from .package import Package

from .. import fileutil


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
                        fileset.update(fileutil.get_file_list(_file, None,
                                                              common.get_file_extentions(self.pkg_conf['package-language'])))
                    else:
                        fileset.add(_file)
            else:
                fileset.update(fileutil.get_file_list(pkg_dir,
                                                      npm_ignore_list(),
                                                      common.get_file_extentions(self.pkg_conf['package-language'])))

        return fileset

    def is_a_node_pkg(self, pkg_dir):
        return True if (self.pkg_conf['build-sys'] == 'npm' and
                        osp.isfile(osp.join(pkg_dir, 'package.json'))) else False

    def get_src_files(self, pkg_dir, exclude_filter):

        fileset = self.get_nodejs_files(pkg_dir)

        file_filters = fileutil.get_file_filters(pkg_dir, exclude_filter.split(','))
        fileset = fileset.difference(file_filters.exclude_files)

        fileset = fileset.difference(_file for _file in fileset
                                     for exdir in file_filters.exclude_dirs
                                     if _file.startswith(osp.join(exdir, '')))

        return fileset

    def get_build_cmd(self):
        return 'npm install'


class ComposerPkg(Package):

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        Package.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

    def get_build_cmd(self):
        return 'php ${VMINPUTDIR}/composer.phar install --no-interaction --no-progress'


class PearPkg(Package):

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        Package.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

    def get_build_cmd(self):
        return 'pear config-set php_dir ${BUILD_DIR}/user_lib && pear install --alldeps --register-only ${VMINPUTDIR}/%s' % self.pkg_conf['package-archive']
