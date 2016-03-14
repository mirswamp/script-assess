import os
import re
import shutil
import os.path as osp
import logging
from abc import ABCMeta
import xml.etree.ElementTree as ET
import yaml

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
        return "No files with '.rb' extenstion found in %s" % self.pkg_dir


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


class BuildSummaryRubyNoGem(BuildSummary):

    def __init__(self, build_root_dir, pkg_root_dir, pkg_conf):
        BuildSummary.__init__(self, build_root_dir, pkg_root_dir, pkg_conf)
        BuildSummary._add(self._root, 'package-dir', pkg_conf['package-dir'])
        self.build_root_dir = build_root_dir

    def add_build_artifacts(self, include, exclude, libs):

        build_artifacts_xml = BuildSummary._add(self._root, 'build-artifacts')
        ruby_gem_xml = BuildSummary._add(build_artifacts_xml, 'ruby-src')


        ruby_src_xml = BuildSummary._add(ruby_gem_xml, 'include')
        for _file in include:
            filepath = osp.relpath(_file, self.build_root_dir)
            BuildSummary._add(ruby_src_xml, 'file', filepath)

        ruby_src_xml = BuildSummary._add(ruby_gem_xml, 'exclude')
        for _file in exclude:
            filepath = osp.relpath(_file, self.build_root_dir)
            BuildSummary._add(ruby_src_xml, 'file', filepath)

        ruby_dep_xml = BuildSummary._add(ruby_gem_xml, 'dependency')
        for _file in libs:
            BuildSummary._add(ruby_dep_xml, 'file', _file)


class BuildSummaryRubyGem(BuildSummary):

    def __init__(self, build_root_dir, pkg_root_dir, pkg_conf):
        BuildSummary.__init__(self, build_root_dir, pkg_root_dir, pkg_conf)
        self.build_root_dir = build_root_dir
        self.pkg_root_dir = pkg_root_dir

    def add_build_artifacts(self, gem_name, gem_version, gem_platform,
                            fileset, depenencies):

        BuildSummary._add(self._root, 'gem-name', gem_name)
        BuildSummary._add(self._root, 'gem-version', gem_version)
        BuildSummary._add(self._root, 'gem-platform', gem_platform)
        gem_dir = '{0}-{1}'.format(gem_name, gem_version)
        BuildSummary._add(self._root, 'package-dir', gem_dir)

        build_artifacts_xml = BuildSummary._add(self._root, 'build-artifacts')
        ruby_gem_xml = BuildSummary._add(build_artifacts_xml, 'ruby-src')
        ruby_src_xml = BuildSummary._add(ruby_gem_xml, 'include')

        gem_dir = '{0}-{1}'.format(gem_name, gem_version)
        for _file in fileset:
            if osp.splitext(_file)[1] == '.rb':
                filepath = osp.join(osp.join(self.pkg_root_dir, gem_dir), _file)
                BuildSummary._add(ruby_src_xml, 'file', filepath)

        ruby_dep_xml = BuildSummary._add(ruby_gem_xml, 'dependency')
        for _file in depenencies:
            BuildSummary._add(ruby_dep_xml, 'file', _file)


class RubyPkg:

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        pass

    def build(self, build_root_dir):
        raise NotImplementedError()

    @classmethod
    def get_env(cls, pwd):
        new_env = dict(os.environ)
        if 'PWD' in new_env:
            new_env['PWD'] = pwd

        return new_env

    @classmethod
    def run_cmd(cls, cmd, cwd, outfile, errfile, description, shell=False):

        environ = RubyPkg.get_env(cwd)

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


class RubySrc(RubyPkg):

    PKG_ROOT_DIRNAME = "pkg1"

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        RubyPkg.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

        self.pkg_conf = confreader.read_conf_into_dict(pkg_conf_file)

        with LogTaskStatus('package-unarchive'):
            pkg_archive = osp.join(input_root_dir, self.pkg_conf['package-archive'])
            pkg_root_dir = osp.join(build_root_dir, RubyNoBuild.PKG_ROOT_DIRNAME)
            status = utillib.unpack_archive(pkg_archive, pkg_root_dir, True)

            if status != 0:
                raise UnpackArchiveError(osp.basename(pkg_archive))

            pkg_dir = osp.join(pkg_root_dir, self.pkg_conf['package-dir'])

            if not osp.isdir(pkg_dir):
                raise NotADirectoryException(osp.basename(pkg_dir))
            else:
                self.pkg_dir = pkg_dir

    def _get_files(self, exclude_str):
        include = set()
        exclude = set()
        exclude_dir = set()
        dirs = set()

        if exclude_str:
            for xpath in exclude_str.split(','):
                if xpath.strip():
                    if osp.isdir(osp.join(self.pkg_dir, xpath)):
                        exclude_dir.add(osp.join(self.pkg_dir, xpath))
                    elif osp.isfile(osp.join(self.pkg_dir, xpath)):
                        exclude.add(osp.join(self.pkg_dir, xpath))
                    else:
                        logging.warning('Exclude path %s not found',
                                        osp.join(self.pkg_dir, xpath))


        for dirpath, _, filenames in utillib.os_walk(self.pkg_dir, exclude_dir):
            rb_files = {osp.join(dirpath, _file) for _file in filenames \
                        if osp.splitext(_file)[1] == '.rb'}
            if rb_files:
                if dirpath not in exclude_dir:
                    include.update(rb_files)
                    dirs.add(dirpath)
                else:
                    exclude.update(rb_files)

        include.difference_update(exclude)
        return (include, exclude, dirs)

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

                (exit_code, environ) = RubyPkg.run_cmd(config_cmd,
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


class RubyBundlerRake(RubySrc):

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        RubySrc.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

    @classmethod
    def _install_bundler(cls, build_root_dir, build_summary):

        gem_install_cmd = ['gem', 'install', '--no-document', 'bundler']

        outfile = osp.join(build_root_dir, 'install_bundler_gem.out')
        errfile = osp.join(build_root_dir, 'install_bundler_gem.err')

        (exit_code, environ) = RubyPkg.run_cmd(gem_install_cmd,
                                               build_root_dir,
                                               outfile,
                                               errfile,
                                               "INSTALL BUNDLER")

        build_summary.add_command('install-bundler', gem_install_cmd[0],
                                  gem_install_cmd[1:], exit_code, environ,
                                  build_root_dir,
                                  outfile, errfile)

        if exit_code != 0:
            build_summary.add_exit_code(exit_code)
            raise CommandFailedError(gem_install_cmd, exit_code,
                                     BuildSummary.FILENAME,
                                     osp.relpath(outfile, build_root_dir),
                                     osp.relpath(errfile, build_root_dir))

    def build(self, build_root_dir):

        with BuildSummaryRubyNoGem(build_root_dir,
                                   RubyGem.PKG_ROOT_DIRNAME,
                                   self.pkg_conf) as build_summary:

            self._configure(build_root_dir, build_summary)

            with LogTaskStatus('build'):

                RubyBundlerRake._install_bundler(build_root_dir, build_summary)

                bundle_install_cmd = ['bundle', 'install']
                outfile = osp.join(build_root_dir, 'bundle_install.out')
                errfile = osp.join(build_root_dir, 'bundle_install.err')

                (exit_code, environ) = RubyPkg.run_cmd(bundle_install_cmd,
                                                       self.pkg_dir,
                                                       outfile,
                                                       errfile,
                                                       "'bundle install'")

                build_summary.add_command('bundle-install', bundle_install_cmd[0],
                                          bundle_install_cmd[1:], exit_code, environ,
                                          environ['PWD'],
                                          outfile, errfile)

                if exit_code != 0:
                    build_summary.add_exit_code(exit_code)
                    raise CommandFailedError(bundle_install_cmd, exit_code,
                                             BuildSummary.FILENAME,
                                             osp.relpath(outfile, build_root_dir),
                                             osp.relpath(errfile, build_root_dir))

                if self.pkg_conf['build-sys'].endswith('+rake'):

                    pkg_build_dir = osp.normpath(osp.join(self.pkg_dir,
                                                          self.pkg_conf.get('build-dir', '.')))

                    build_cmd = 'bundle exec rake --nosystem --nosearch --rakefile %s %s' % \
                                (self.pkg_conf.get('build-file', 'Rakefile'), \
                                 self.pkg_conf.get('build-target', ''))

                    outfile = osp.join(build_root_dir, 'build_stdout.out')
                    errfile = osp.join(build_root_dir, 'build_stderr.err')

                    (exit_code, environ) = RubyPkg.run_cmd(build_cmd,
                                                           pkg_build_dir,
                                                           outfile,
                                                           errfile,
                                                           "'rake'")

                    build_summary.add_command('rake', build_cmd,
                                              [], exit_code, environ,
                                              environ['PWD'],
                                              outfile, errfile)

                    if exit_code != 0:
                        build_summary.add_exit_code(exit_code)
                        raise CommandFailedError(build_cmd, exit_code,
                                                 BuildSummary.FILENAME,
                                                 osp.relpath(outfile, build_root_dir),
                                                 osp.relpath(errfile, build_root_dir))

                elif self.pkg_conf['build-sys'].endswith('+other'):

                    pkg_build_dir = osp.normpath(osp.join(self.pkg_dir,
                                                          self.pkg_conf.get('build-dir', '.')))

                    build_cmd = 'bundle exec %s %s %s %s' % (self.pkg_conf['build-cmd'], \
                                                             self.pkg_conf.get('build-file', ''), \
                                                             self.pkg_conf.get('build-opt', ''), \
                                                             self.pkg_conf.get('build-target', ''))

                    outfile = osp.join(build_root_dir, 'build_stdout.out')
                    errfile = osp.join(build_root_dir, 'build_stderr.err')

                    (exit_code, environ) = RubyPkg.run_cmd(build_cmd,
                                                           pkg_build_dir,
                                                           outfile,
                                                           errfile,
                                                           "'rake'")

                    build_summary.add_command('rake', build_cmd,
                                              [], exit_code, environ,
                                              environ['PWD'],
                                              outfile, errfile)

                    if exit_code != 0:
                        build_summary.add_exit_code(exit_code)
                        raise CommandFailedError(build_cmd, exit_code,
                                                 BuildSummary.FILENAME,
                                                 osp.relpath(outfile, build_root_dir),
                                                 osp.relpath(errfile, build_root_dir))

                include, exclude, dirs = self._get_files(self.pkg_conf.get('package-exclude-paths', None))

                if len(include) == 0:
                    err = EmptyPackageError(osp.basename(self.pkg_dir),
                                            BuildSummary.FILENAME)
                    build_summary.add_exit_code(err.exit_code)
                    raise err
                else:
                    build_summary.add_exit_code(0)
                    build_summary.add_build_artifacts(include, exclude, dirs)
                    return (0, BuildSummary.FILENAME)


class RubyRake(RubySrc):

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        RubySrc.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

    def _get_build_command_old(self):

        if self.pkg_conf['build-sys'] == 'rake':
            build_cmd = ['rake',
                         '--nosystem', '--nosearch',
                         '--rakefile', self.pkg_conf.get('build-file', 'Rakefile')]

            if 'build-target' in self.pkg_conf:
                build_cmd.append(self.pkg_conf['build-target'])

            if 'build-opt' in self.pkg_conf:
                build_cmd.extend(self.pkg_conf['build-opt'].split())

        else:
            build_cmd = ['/bin/bash', '-c']

            build_cmd.append('{0} {1} {2} {3}'.format(self.pkg_conf['build-cmd'],
                                                      self.pkg_conf.get('build-file', ''),
                                                      self.pkg_conf.get('build-opt', ''),
                                                      self.pkg_conf.get('build-target', '')))

        return build_cmd

    def _get_build_command(self):

        if self.pkg_conf['build-sys'] == 'rake':
            build_cmd = 'rake --nosystem --nosearch --rakefile %s %s %s' % \
                        (self.pkg_conf.get('build-file', 'Rakefile'), \
                         self.pkg_conf.get('build-target', ''), \
                         self.pkg_conf.get('build-opt', ''))
        else:
            build_cmd = '%s %s %s %s' % (self.pkg_conf['build-cmd'],
                                         self.pkg_conf.get('build-file', ''),
                                         self.pkg_conf.get('build-opt', ''),
                                         self.pkg_conf.get('build-target', ''))

        return build_cmd

    def build(self, build_root_dir):

        with BuildSummaryRubyNoGem(build_root_dir,
                                   RubyGem.PKG_ROOT_DIRNAME,
                                   self.pkg_conf) as build_summary:

            self._configure(build_root_dir, build_summary)

            with LogTaskStatus('build'):

                pkg_build_dir = osp.normpath(osp.join(self.pkg_dir,
                                                      self.pkg_conf.get('build-dir', '.')))

                build_cmd = self._get_build_command()
                outfile = osp.join(build_root_dir, 'build_stdout.out')
                errfile = osp.join(build_root_dir, 'build_stderr.err')

                (exit_code, environ) = RubyPkg.run_cmd(build_cmd,
                                                       pkg_build_dir,
                                                       outfile,
                                                       errfile,
                                                       'rake')

                build_summary.add_command('rake', build_cmd,
                                          [], exit_code, environ,
                                          environ['PWD'],
                                          outfile, errfile)

                if exit_code != 0:
                    build_summary.add_exit_code(exit_code)
                    raise CommandFailedError(build_cmd, exit_code,
                                             BuildSummary.FILENAME,
                                             osp.relpath(outfile, build_root_dir),
                                             osp.relpath(errfile, build_root_dir))

                include, exclude, dirs = self._get_files(self.pkg_conf.get('package-exclude-paths',
                                                                           None))

                if len(include) == 0:
                    err = EmptyPackageError(osp.basename(self.pkg_dir),
                                            BuildSummary.FILENAME)
                    build_summary.add_exit_code(err.exit_code)
                    raise err
                else:
                    build_summary.add_exit_code(0)
                    build_summary.add_build_artifacts(include, exclude, dirs)
                    return (0, BuildSummary.FILENAME)


class RubyNoBuild(RubySrc):

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        RubySrc.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

    def build(self, build_root_dir):

        with BuildSummaryRubyNoGem(build_root_dir,
                                   RubyGem.PKG_ROOT_DIRNAME,
                                   self.pkg_conf) as build_summary:

            with LogTaskStatus('build'):

                include, exclude, dirs = self._get_files(self.pkg_conf.get('package-exclude-paths', None))
                if len(include) == 0:
                    err = EmptyPackageError(osp.basename(self.pkg_dir),
                                            BuildSummary.FILENAME)
                    build_summary.add_exit_code(err.exit_code)
                    raise err
                else:
                    build_summary.add_exit_code(0)
                    build_summary.add_build_artifacts(include, exclude, dirs)
                    return (0, BuildSummary.FILENAME)


class RubyGem(RubyPkg):
    '''Class to handle RubyGems'''

    # Install the gem check for errors 'gem install <path to XXX.gem> --user-install'
    # Read the spec 'gem spec <path to XXX.gem> --yaml > XXX.yaml'
    # Rewrite the yaml without Ruby class info re.compile(':\s+!ruby/object:Gem::.+$')
    # yaml.load('XXX.yamlnoruby') and get version, name, platform, dependencies, files
    # Unpack the gem in build/pkg1
    # Write build_summary.xml

    PKG_ROOT_DIRNAME = "pkg1"
    GEM_HOME = 'GEM_HOME'

    def __init__(self, pkg_conf_file, input_root_dir, build_root_dir):
        RubyPkg.__init__(self, pkg_conf_file, input_root_dir, build_root_dir)

        self.pkg_conf = confreader.read_conf_into_dict(pkg_conf_file)
        self.gem_file = osp.join(input_root_dir, self.pkg_conf['package-archive'])

    @classmethod
    def rm_ruby_code(cls, filename):
        '''remove ruby object specific code from specification file'''
        regex = re.compile('!ruby/object:Gem::.+$')
        new_file = filename + '-modified'

        with open(filename) as fobj:
            with open(new_file, 'w') as new_fobj:
                for line in fobj:
                    newline = regex.sub('', line)
                    new_fobj.write(newline)

        return new_file

    @classmethod
    def get_dependencies(cls, gem_spec):

        gem_user_dir = osp.join(os.getenv(RubyGem.GEM_HOME), 'gems')
        user_dependencies = []

        gem_dir = '{0}-{1}'.format(gem_spec['name'], gem_spec['version']['version'])
        user_dependencies.append(osp.join(osp.join(gem_user_dir, gem_dir), 'lib'))

        spec_dependencies = [dep['name'] for dep in gem_spec['dependencies']]
        for spec_dep in sorted(spec_dependencies):
            for gem in os.listdir(gem_user_dir):
                if gem.startswith(spec_dep + '-'):
                    user_dependencies.append(osp.join(osp.join(gem_user_dir, gem), 'lib'))

        return user_dependencies

    def build(self, build_root_dir):
        #call `gem install filename.gem`

        with BuildSummaryRubyGem(build_root_dir,
                                 RubyGem.PKG_ROOT_DIRNAME,
                                 self.pkg_conf) as build_summary:

            pkg_root_dir = osp.join(build_root_dir, RubyGem.PKG_ROOT_DIRNAME)
            if not osp.isdir(pkg_root_dir):
                os.makedirs(pkg_root_dir, exist_ok=True)

            with LogTaskStatus('gem-install'):

                gem_install_cmd = ['gem', 'install',
                                   '--no-document',
                                   self.gem_file]

                outfile = osp.join(build_root_dir, 'install.out')
                errfile = osp.join(build_root_dir, 'install.err')

                (exit_code, environ) = RubyPkg.run_cmd(gem_install_cmd,
                                                       build_root_dir,
                                                       outfile,
                                                       errfile,
                                                       "GEM INSTALL")

                build_summary.add_command('gem-install', gem_install_cmd[0],
                                          gem_install_cmd[1:], exit_code, environ,
                                          build_root_dir,
                                          outfile, errfile)

                if exit_code != 0:
                    build_summary.add_exit_code(exit_code)
                    raise CommandFailedError(gem_install_cmd, exit_code,
                                             BuildSummary.FILENAME,
                                             osp.relpath(outfile, build_root_dir),
                                             osp.relpath(errfile, build_root_dir))


            with LogTaskStatus('gem-unpack'):

                gem_unpack_cmd = 'gem unpack %s --target %s' % (self.gem_file,
                                                                pkg_root_dir)

                outfile = osp.join(build_root_dir, 'unpack.out')
                errfile = osp.join(build_root_dir, 'unpack.err')

                (exit_code, environ) = RubyPkg.run_cmd(gem_unpack_cmd,
                                                       build_root_dir,
                                                       outfile,
                                                       errfile,
                                                       "GEM UNPACK")

                build_summary.add_command('gem-unpack', gem_unpack_cmd,
                                          [], exit_code, environ,
                                          build_root_dir, outfile, errfile)

                if exit_code != 0:
                    build_summary.add_exit_code(exit_code)
                    raise CommandFailedError(gem_unpack_cmd, exit_code,
                                             BuildSummary.FILENAME,
                                             osp.relpath(outfile, build_root_dir),
                                             osp.relpath(errfile, build_root_dir))

            with LogTaskStatus('read-gem-spec'):

                gem_spec_cmd = ['gem', 'specification', self.gem_file, '--yaml']

                outfile = osp.join(build_root_dir,
                                   osp.splitext(osp.basename(self.gem_file))[0] + '.yaml')
                errfile = osp.join(build_root_dir,
                                   osp.splitext(osp.basename(self.gem_file))[0] + '-spec.err')

                (exit_code, environ) = RubyPkg.run_cmd(gem_spec_cmd,
                                                       build_root_dir,
                                                       outfile,
                                                       errfile,
                                                       "GEM UNPACK")

                build_summary.add_command('read-gem-spec', gem_spec_cmd[0],
                                          gem_spec_cmd[1:], exit_code, environ,
                                          build_root_dir, outfile, errfile)

                if exit_code != 0:
                    build_summary.add_exit_code(exit_code)
                    raise CommandFailedError(gem_spec_cmd, exit_code,
                                             BuildSummary.FILENAME,
                                             osp.relpath(outfile, build_root_dir),
                                             osp.relpath(errfile, build_root_dir))

                with open(RubyGem.rm_ruby_code(outfile)) as fobj:
                    gem_spec = yaml.load(fobj)

                if 'files' not in gem_spec.keys():
                    raise EmptyPackageError("{0}-{1}".format(gem_spec['name'],
                                                             gem_spec['version']['version']),
                                            BuildSummary.FILENAME)

                src_files = {f for f in gem_spec['files'] if osp.splitext(f)[1] == '.rb'}

                if 'test_files' in gem_spec.keys():
                    test_files = {f for f in gem_spec['test_files'] \
                                  if osp.splitext(f)[1] == '.rb'}
                    src_files = src_files.difference(test_files)

                logging.info(src_files)

                depenencies = RubyGem.get_dependencies(gem_spec)

                build_summary.add_exit_code(exit_code)
                build_summary.add_build_artifacts(gem_spec['name'],
                                                  gem_spec['version']['version'],
                                                  gem_spec['platform'],
                                                  src_files, depenencies)

        return (exit_code, BuildSummary.FILENAME)

def get_pkg_obj(pkg_conf_file, input_root_dir, build_root_dir):

    pkg_conf = confreader.read_conf_into_dict(pkg_conf_file)

    #if ('package-language' not in pkg_conf) or \
    #   (pkg_conf['package-language'] != 'Ruby'):
    #    raise NotImplementedError("'package-language' in package.conf must be Ruby")


    ruby_pkg_types = {
        'rubygems' : RubyGem, #rubygems is deprecated, will be deleted in the future
        'ruby-gem' : RubyGem,
        'no-build' : RubyNoBuild,
        'bundler+rake' : RubyBundlerRake,
        'bundler+other' : RubyBundlerRake,
        'bundler' : RubyBundlerRake,
        'rake' : RubyRake,
        'other' : RubyRake
    }

    build_sys = pkg_conf['build-sys']

    if build_sys in ruby_pkg_types.keys():
        return ruby_pkg_types[build_sys](pkg_conf_file, input_root_dir, build_root_dir)
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

