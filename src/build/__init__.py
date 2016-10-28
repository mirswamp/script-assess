import os
import os.path as osp
import shutil
import logging

from .web_package import JsNodePkg
from .python_package import PythonDistUtilsPkg
from .python_package import PythonWheelPkg
from .python_package import PythonOtherPkg
from .common import EmptyPackageError
from .common import CommandFailedError

from .. import utillib
from .. import confreader
from ..logger import LogTaskStatus

from ..utillib import UnpackArchiveError
from ..utillib import NotADirectoryException


def get_pkg_obj(pkg_conf_file, input_root_dir, build_root_dir):

    pkg_conf = confreader.read_conf_into_dict(pkg_conf_file)

    web_pkg_types = {
        'npm': JsNodePkg,
        'composer': JsNodePkg,
        'pear': JsNodePkg,
        'no-build': JsNodePkg,
        'python-distutils': PythonDistUtilsPkg,
        'python-setuptools': PythonDistUtilsPkg,
        'wheels': PythonWheelPkg,
        'other': PythonOtherPkg
        'none': PythonOtherPkg
    }

    build_sys = pkg_conf['build-sys']

    if build_sys in web_pkg_types.keys():
        return web_pkg_types[build_sys](pkg_conf_file, input_root_dir, build_root_dir)
    else:
        raise NotImplementedError("Unknown build system '{0}'".format(build_sys))


def build(input_root_dir, output_root_dir, build_root_dir):

    try:
        if not osp.isdir(build_root_dir):
            os.makedirs(build_root_dir, exist_ok=True)

        pkg_conf_file = osp.join(input_root_dir, 'package.conf')
        pkg_obj = get_pkg_obj(pkg_conf_file, input_root_dir, build_root_dir)
        exit_code, build_summary_file = pkg_obj.build(build_root_dir)
    except (UnpackArchiveError,
            NotADirectoryException,
            EmptyPackageError,
            CommandFailedError,
            NotImplementedError) as err:
        logging.exception(err)
        if hasattr(err, 'exit_code'):
            exit_code = err.exit_code
        else:
            exit_code = 1

        if hasattr(err, 'build_summary_file'):
            build_summary_file = err.build_summary_file
        else:
            build_summary_file = None

    finally:
        build_conf = dict()
        build_conf['exit-code'] = str(exit_code)

        if build_summary_file:
            build_conf['build-summary-file'] = osp.basename(build_summary_file)

        with LogTaskStatus('build-archive'):
            build_archive = shutil.make_archive(osp.join(output_root_dir, 'build'),
                                                'gztar',
                                                osp.dirname(build_root_dir),
                                                osp.basename(build_root_dir))

            build_conf['build-archive'] = osp.basename(build_archive)
            build_conf['build-root-dir'] = osp.basename(build_root_dir)

            utillib.write_to_file(osp.join(output_root_dir, 'build.conf'), build_conf)

    return (exit_code, build_summary_file)
