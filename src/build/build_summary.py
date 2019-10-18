import os.path as osp
import xml.etree.ElementTree as ET
import logging

from .common import LANG_EXT_MAPPING
from .. import utillib


class BuildSummary:

    FILENAME = 'build_summary.xml'
    PKG_SRC_TAG = 'pkg-src'

    @classmethod
    def _add(cls, parent, tag, text=None):
        elem = ET.SubElement(parent, tag)
        if text:
            elem.text = text

        return elem

    def __init__(self, build_root_dir, pkg_root_dir, pkg_conf):

        self._build_root_dir = build_root_dir
        self._root = ET.Element('build-summary')

        pkg_conf_xml = BuildSummary._add(self._root, 'package-conf')

        for key in pkg_conf.keys():
            BuildSummary._add(pkg_conf_xml, key, pkg_conf[key])

        BuildSummary._add(self._root, 'build-root-dir', build_root_dir)
        BuildSummary._add(self._root, 'package-root-dir', pkg_root_dir)
        BuildSummary._add(self._root, 'platform', utillib.platform())
        BuildSummary._add(self._root, 'uuid', utillib.get_uuid())
        BuildSummary._add(self._root, 'package-dir', pkg_conf['package-dir'])
        BuildSummary._add(self._root, 'build-fw', 'script-assess')
        BuildSummary._add(self._root, 'build-fw-version', utillib.get_framework_version())

    def __enter__(self):
        return self

    def __exit__(self, exception_type, value, traceback):
        if value:
            logging.exception(value)

        tree = ET.ElementTree(self._root)
        build_summary_file = osp.join(self._build_root_dir, BuildSummary.FILENAME)
        tree.write(build_summary_file, encoding='UTF-8', xml_declaration=True)

    def add_to_root(self, elem):
        self._root.append(elem)

    def add_command(self, cmd_type, executable, args,
                    exit_code, environ, working_dir,
                    stdout_file, stderr_file):

        cmd_root_xml = BuildSummary._add(self._root, 'build-command')
        cmd_root_xml.set('type', cmd_type)

        BuildSummary._add(cmd_root_xml, 'cwd', working_dir)
        environ_xml = BuildSummary._add(cmd_root_xml, 'environment')
        for _env in environ.keys():
            BuildSummary._add(environ_xml, 'env',
                              '{0}={1}'.format(_env, environ[_env]))

        BuildSummary._add(cmd_root_xml, 'executable', executable)
        args_xml = BuildSummary._add(cmd_root_xml, 'args')
        for _arg in args:
            if _arg:
                BuildSummary._add(args_xml, 'arg', _arg)

        BuildSummary._add(cmd_root_xml, 'exit-code', str(exit_code))
        BuildSummary._add(cmd_root_xml, 'stdout-file', stdout_file)
        BuildSummary._add(cmd_root_xml, 'stderr-file', stderr_file)

    def add_exit_code(self, exit_code):
        if exit_code >= 0:
            BuildSummary._add(self._root, 'exit-code', str(exit_code))
        elif exit_code < 0:
            BuildSummary._add(self._root, 'exit-signal', str(abs(exit_code)))

    def _add_file_set(self, parent_xml, xml_tag, fileset):
        xml_elem = BuildSummary._add(parent_xml, xml_tag)
        for _file in fileset:
            BuildSummary._add(xml_elem, 'file',
                              osp.relpath(_file, self._build_root_dir))

    def add_build_artifacts(self, fileset, pkg_lang):

        build_artifacts_xml = BuildSummary._add(self._root, 'build-artifacts')
        pkg_xml = BuildSummary._add(build_artifacts_xml, BuildSummary.PKG_SRC_TAG)

        if isinstance(pkg_lang, str):
            pkg_lang = pkg_lang.lower().split()

        for lang, ext in LANG_EXT_MAPPING.items():
            if lang in pkg_lang:
                files = [_file for _file in fileset
                         if osp.splitext(_file)[1] in ext]

                if files:
                    self._add_file_set(pkg_xml, '{0}-src'.format(lang), files)
