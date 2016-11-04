import os
import os.path as osp
import logging
from .logger import LogTaskStatus

from . import utillib
from . import confreader


class InstallOSDependenciesFailedError(Exception):

    def __init__(self, *args):
        Exception.__init__(self, *args)
        self.retry = True


def install(input_dir):
    '''Raises InstallOSDependenciesFailedError if fails'''

    with LogTaskStatus('install-os-dependencies') as status_dot_out:
        exit_code = 0

        os_deps_file = osp.join(input_dir, 'os-dependencies.conf')

        if not osp.isfile(os_deps_file):
            status_dot_out.skip_task('{0} Not Found'.format(osp.basename(os_deps_file)))
            logging.info('File %s not found, skipping install-os-dependencies', os_deps_file)
        else:
            os_deps = confreader.read_conf_into_dict(os_deps_file)
            this_platform_deps = 'dependencies-{0}'.format(os.getenv('VMPLATNAME'))

            if this_platform_deps in os_deps:
                if os_deps[this_platform_deps]:
                    pkg_installer = os.getenv('VMOSPACKAGEINSTALL')
                    exit_code, _ = utillib.run_cmd([pkg_installer, os_deps_file],
                                                   description='OS DEPENDENCIES INSTALLATION')
                    status_dot_out.update_task_status(exit_code)

                    if exit_code != 0:
                        raise InstallOSDependenciesFailedError("Failed to install dependencies '{0}'".format(os_deps[this_platform_deps]))

                else:
                    status_dot_out.skip_task('none')
                    logging.info('This platform needs no additional packages to be installed')
            else:
                status_dot_out.skip_task('none')
                logging.info('The current platform %s not present in the file %s',
                             this_platform_deps,
                             os_deps_file)

    return exit_code
