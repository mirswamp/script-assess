import os
import re
import shutil
import os.path as osp
import logging
import json
import glob
from abc import ABCMeta
import xml.etree.ElementTree as ET

from . import utillib
from . import confreader
from .logger import LogTaskStatus

from .utillib import UnpackArchiveError
from .utillib import NotADirectoryException

from . import utillib


class EmptyPackageError(Exception):

    def __init__(self, pkg_dir, build_summary_file):
        Exception.__init__(self)
        self.pkg_dir = pkg_dir
        self.build_summary_file = build_summary_file
        self.exit_code = 2

    def __str__(self):
        return "No files with '.js', '.html', '.css' or '.xml' extenstion found in %s" % self.pkg_dir


class CommandFailedError(Exception):

    def __init__(self, command, exit_code, build_summary_file, outfile, errfile):
        Exception.__init__(self)
        self.command = ' '.join(command) if isinstance(command, list) else command
        self.exit_code = exit_code
        self.build_summary_file = build_summary_file
        self.outfile = outfile
        self.errfile = errfile

    def __str__(self):

        disp_str = "Command '{0}' failed with exit-code '{1}'".format(self.command,
                                                                      self.exit_code)

        if self.outfile and self.errfile:
            disp_str += ", See "

            if self.outfile:
                disp_str += "'{0}'".format(self.outfile)

                if self.errfile:
                    disp_str += ", "

            if self.errfile:
                disp_str += "'{0}'".format(self.errfile)

            disp_str += " for errors"

        return disp_str


class BuildSummary(metaclass=ABCMeta):

    FILENAME = 'build_summary.xml'

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

    def __enter__(self):
        return self

    def __exit__(self, exception_type, value, traceback):
        if value:
            logging.exception(value)

        tree = ET.ElementTree(self._root)
        build_summary_file = osp.join(self._build_root_dir, BuildSummary.FILENAME)
        tree.write(build_summary_file, encoding='UTF-8', xml_declaration=True)

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


class BuildSummaryJavascript(BuildSummary):

    def __init__(self, build_root_dir, pkg_root_dir, pkg_conf):
        BuildSummary.__init__(self, build_root_dir, pkg_root_dir, pkg_conf)
        BuildSummary._add(self._root, 'package-dir', pkg_conf['package-dir'])
        self.build_root_dir = build_root_dir

    def _add_file_set(self, parent_xml, xml_tag, fileset, ):
        xml_elem = BuildSummary._add(parent_xml, xml_tag)
        for _file in fileset:
            BuildSummary._add(xml_elem, 'file',
                              osp.relpath(_file, self.build_root_dir))
        
    def add_build_artifacts(self, fileset):

        build_artifacts_xml = BuildSummary._add(self._root, 'build-artifacts')
        web_xml = BuildSummary._add(build_artifacts_xml, 'web-src')

        for lang, ext in JsPkg.LANG_EXT_MAPPING.items():
            if isinstance(ext, str):
                files = [_file for _file in fileset \
                         if osp.splitext(_file)[1] == ext]
            else:
                files = [_file for _file in fileset \
                         if osp.splitext(_file)[1] in ext]
            
            if files:
                self._add_file_set(web_xml, lang, files)

    def add_build_artifacts_old(self, fileset):

        build_artifacts_xml = BuildSummary._add(self._root, 'build-artifacts')
        web_xml = BuildSummary._add(build_artifacts_xml, 'web-src')

        js_fileset = [_file for _file in fileset \
                      if osp.splitext(_file)[1] == '.js']

        if js_fileset:
            self._add_file_set(web_xml, 'javascript', js_fileset)

        html_fileset = [_file for _file in fileset \
                        if osp.splitext(_file)[1] in ['.htm', '.html']]
        
        if html_fileset:
            self._add_file_set(web_xml, 'html', html_fileset)

        css_fileset = [_file for _file in fileset \
                       if osp.splitext(_file)[1] == '.css']

        if css_fileset:
            self._add_file_set(web_xml, 'css', css_fileset)


        xml_fileset = [_file for _file in fileset \
                       if osp.splitext(_file)[1] == '.xml']

        if xml_fileset:
            self._add_file_set(web_xml, 'xml', xml_fileset)

class JsPkg:

    PKG_ROOT_DIRNAME = "pkg1"
    WEB_FILE_TYPES = ['.js', '.html', '.css', '.xml']
    LANG_EXT_MAPPING = { 'javascript' : '.js',
                         'html' : ['.html', '.htm'],
                         'css' : '.css',
                         'xml' : '.xml',
                         'php' : '.php',
    }

    @classmethod
    def get_file_types(cls, pkg_lang):
        '''pkg_lang is a string'''

        ext_list = []
        for lang in pkg_lang.split():
            ext = JsPkg.LANG_EXT_MAPPING[lang.lower()]
            if isinstance(ext, str):
                ext_list.append(ext)
            else:
                ext_list.extend(ext)
        return ext_list

    @classmethod
    def get_env(cls, pwd):
        new_env = dict(os.environ)
        if 'PWD' in new_env:
            new_env['PWD'] = pwd

        return new_env

    @classmethod
    def run_cmd(cls, cmd, cwd, outfile, errfile, description, shell=False):

        environ = JsPkg.get_env(cwd)

        logging.info('%s COMMAND %s', description, cmd)

        (exit_code, _environ) = utillib.run_cmd(cmd,
                                                outfile=outfile,
                                                errfile=errfile,
                                                infile=None,
                                                cwd=environ['PWD'],
                                                shell=shell,
                                                env=environ)

        logging.info('%s WORKING DIR %s', description, environ['PWD'])
        logging.info('%s EXIT CODE %s', description, exit_code)
        logging.info('%s ENVIRONMENT %s', description, _environ)

        return (exit_code, _environ)
    
    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):

        self.pkg_conf = confreader.read_conf_into_dict(pkg_conf_file)

        with LogTaskStatus('package-unarchive'):
            pkg_archive = osp.join(input_root_dir, self.pkg_conf['package-archive'])
            pkg_root_dir = osp.join(build_root_dir, JsPkg.PKG_ROOT_DIRNAME)
            status = utillib.unpack_archive(pkg_archive, pkg_root_dir, True)

            if status != 0:
                raise UnpackArchiveError(osp.basename(pkg_archive))

            pkg_dir = osp.join(pkg_root_dir, self.pkg_conf['package-dir'])

            if not osp.isdir(pkg_dir):
                raise NotADirectoryException(osp.basename(pkg_dir))
            else:
                self.pkg_dir = pkg_dir

    def _configure(self, build_root_dir, build_summary):

        with LogTaskStatus('configure') as status_dot_out:

            if 'config-cmd' not in self.pkg_conf \
               or len(self.pkg_conf['config-cmd'].strip()) == 0:
                status_dot_out.skip_task()
            else:
                config_dir = osp.normpath(osp.join(self.pkg_dir,
                                                   self.pkg_conf.get('config-dir', '.')))

                config_cmd = '%s %s' % (self.pkg_conf['config-cmd'],
                                        self.pkg_conf.get('config-opt', ''))

                outfile = osp.join(build_root_dir, 'config_stdout.out')
                errfile = osp.join(build_root_dir, 'config_stderr.out')

                (exit_code, environ) = JsPkg.run_cmd(config_cmd,
                                                     config_dir,
                                                     outfile,
                                                     errfile,
                                                     "CONFIGURE")

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


class JsNodePkg(JsPkg):

    def get_nodejs_files(self, pkg_dir):

        def npm_ignore_list():
            ignore_file = None

            if osp.isfile(osp.join(pkg_dir, '.npmignore')):
                ignore_file = osp.join(pkg_dir, '.npmignore')
            elif osp.isfile(osp.join(pkg_dir, '.gitignore')):
                ignore_file = osp.join(pkg_dir, '.gitignore')

            if ignore_file:
                with open(ignore_file) as fobj:
                    ignore_patterns = {p.strip().strip('\n') for p in fobj \
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
                for _file in [osp.join(pkg_dir, f) \
                              for f in pkg_json['files']]:
                    if osp.isdir(_file):
                        fileset.update(utillib.get_file_list(_file, None,
                                                             JsPkg.get_file_types(self.pkg_conf['package-language'])))
                    else:
                        fileset.add(_file)
            else:
                fileset.update(utillib.get_file_list(pkg_dir,
                                                     npm_ignore_list(),
                                                     JsPkg.get_file_types(self.pkg_conf['package-language'])))

        return fileset

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        JsPkg.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

    def is_a_node_pkg(self, pkg_dir):
        return True if (self.pkg_conf['build-sys'] == 'npm' and \
                        osp.isfile(osp.join(pkg_dir, 'package.json'))) else False

    def get_src_files(self, pkg_dir, exclude_filter):

        file_filters = utillib.get_file_filters(pkg_dir, exclude_filter.split(','))

        fileset = set()
        if self.is_a_node_pkg(pkg_dir):
            fileset = self.get_nodejs_files(pkg_dir)
        else:
            fileset.update(utillib.get_file_list(pkg_dir,
                                                 None,
                                                 JsPkg.get_file_types(self.pkg_conf['package-language'])))

        fileset = fileset.difference(file_filters.exclude_files)

        fileset = fileset.difference(_file for _file in fileset \
                                     for exdir in file_filters.exclude_dirs \
                                     if _file.startswith(osp.join(exdir, '')))

        return fileset

    def build(self, build_root_dir):

        with BuildSummaryJavascript(build_root_dir,
                                    JsPkg.PKG_ROOT_DIRNAME,
                                    self.pkg_conf) as build_summary:

            self._configure(build_root_dir, build_summary)

            with LogTaskStatus('build'):

                pkg_build_dir = osp.normpath(osp.join(self.pkg_dir,
                                                      self.pkg_conf.get('build-dir', '.')))

                #TODO: Build Command 'npm install'
                if self.pkg_conf['build-sys'] == 'npm':
                    build_cmd = 'npm install'
                else:
                    build_cmd = ':'
                    
                outfile = osp.join(build_root_dir, 'build_stdout.out')
                errfile = osp.join(build_root_dir, 'build_stderr.err')

                exit_code, environ = JsPkg.run_cmd(build_cmd, pkg_build_dir,
                                                   outfile, errfile, "BUILD")
                
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

                fileset = self.get_src_files(pkg_build_dir,
                                             self.pkg_conf.get('package-exclude-paths', ''))

                if len(fileset) == 0:
                    err = EmptyPackageError(osp.basename(self.pkg_dir),
                                            BuildSummary.FILENAME)
                    build_summary.add_exit_code(err.exit_code)
                    raise err
                else:
                    build_summary.add_exit_code(0)
                    build_summary.add_build_artifacts(fileset)
                    return (0, BuildSummary.FILENAME)


def get_pkg_obj(pkg_conf_file, input_root_dir, build_root_dir):

    pkg_conf = confreader.read_conf_into_dict(pkg_conf_file)

    web_pkg_types = {
        'npm' : JsNodePkg,
        'no-build' : JsNodePkg,
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

