import os
import os.path as osp
import re
import uuid
import shutil
import logging
import xml.etree.ElementTree as ET
import fnmatch

from . import gencmd
from . import utillib
from . import confreader
from .logger import LogTaskStatus
from .utillib import UnpackArchiveError
from .build import JsPkg


class ToolInstallFailedError(Exception):

    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)


class BuildArtifactsError(Exception):

    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)


class BuildSummaryError(Exception):

    def __init__(self, field, filename):
        Exception.__init__(self)
        self.value = "No `{0}` tag found in `{1}` file".format(field, filename)

    def __str__(self):
        return repr(self.value)


class BuildArtifactsHelper:

    @classmethod
    def _get_fileset(cls, build_root_dir, xml_elem):
        fileset = list()

        for _file in xml_elem:
            if not osp.isabs(_file.text):
                fileset.append(osp.join(build_root_dir, _file.text))
            else:
                fileset.append(_file.text)

        return fileset

    @classmethod
    def get_artifacts(cls, _id, build_summary, xml_elem):
        artifacts = dict(build_summary)

        artifacts['id'] = _id
        artifacts['srcfile'] = list()

        for elem in xml_elem:
             #['javascript', 'html', 'css', 'xml']:
            if elem.tag in JsPkg.LANG_EXT_MAPPING.keys():
                fileset = BuildArtifactsHelper._get_fileset(artifacts['build-root-dir'],
                                                            elem)
                artifacts[elem.tag] = fileset
                artifacts['srcfile'].extend(fileset)

        return artifacts

    @classmethod
    def _get_build_summary(cls, root):
        '''returns a dictionary'''
        return {elem.tag: elem.text for elem in root
                if(elem.tag not in ['package-conf',
                                    'command',
                                    'build-artifacts',
                                    'build-command'])}

    def __init__(self, build_summary_file):

        root = ET.parse(build_summary_file).getroot()

        if root.tag != 'build-summary':
            raise BuildSummaryError('build-summary', build_summary_file)

        if root.find('exit-code') is None:
            raise BuildSummaryError('exit-code', build_summary_file)
        elif int(root.find('exit-code').text) != 0:
            raise BuildArtifactsError('exit-code not 0 in ' + build_summary_file)

        if root.find('build-root-dir') is None:
            raise BuildSummaryError('build-root-dir', build_summary_file)

        if root.find('build-artifacts') is None:
            raise BuildArtifactsError("No  Source Files or Class Files to Assess! "
                                      "Looks like no files with 'rb' extension were found.")

        self._build_summary = BuildArtifactsHelper._get_build_summary(root)
        self._build_artifacts = root.find('build-artifacts')
        self._package_conf = {elem.tag: elem.text for elem in root.find('package-conf')}

    def __contains__(self, key):
        return True if(key in self._build_summary) else False

    def __getitem__(self, key):
        if key in self._build_summary:
            return self._build_summary[key]
        else:
            return self._package_conf.get(key, None)

    def get_pkg_dir(self):
        return osp.normpath(osp.join(osp.join(self._build_summary['build-root-dir'],
                                              self._build_summary['package-root-dir']),
                                     self._package_conf.get('package-dir', '.')))

    def get_build_artifacts(self, *args):
        ''' this is a generator function
        parses through the xml elements in the tree and
        yeilds objects artifacts that we are interested in provided as a parameter'''

        count = 1

        for elem in self._build_artifacts:
            if (elem.tag == 'web-src') and (elem.tag in args):
                yield BuildArtifactsHelper.get_artifacts(count,
                                                         self._build_summary,
                                                         elem)

            elif (elem.tag == 'no-build') and (elem.tag in args):
                raise NotImplementedError

            count += 1


class AssessmentSummary:

    def __init__(self,
                 filename,
                 build_artifacts_helper,
                 tool_conf):

        self._filename = filename

        self._root = ET.Element('assessment-summary')
        AssessmentSummary._add(self._root, 'assessment-summary-uuid', str(uuid.uuid4()))

        AssessmentSummary._add(self._root, 'build-root-dir',
                               build_artifacts_helper['build-root-dir'])

        AssessmentSummary._add(self._root, 'package-root-dir',
                               osp.join(build_artifacts_helper['build-root-dir'],
                                        build_artifacts_helper['package-root-dir'],
                                        build_artifacts_helper['package-dir']))

        if 'build-summary-uuid' in build_artifacts_helper:
            AssessmentSummary._add(self._root, 'build-summary-uuid',
                                   build_artifacts_helper['build-summary-uuid'])

        AssessmentSummary._add(self._root, 'tool-type', tool_conf['tool-type'])
        AssessmentSummary._add(self._root, 'tool-version', tool_conf['tool-version'])
        AssessmentSummary._add(self._root, 'platform', utillib.platform())
        AssessmentSummary._add(self._root, 'start-ts', utillib.posix_epoch())
        self._assessment_artifacts = AssessmentSummary._add(self._root, 'assessment-artifacts')

    def __enter__(self):
        return self

    @classmethod
    def _add(cls, parent, tag, text=None):
        elem = ET.SubElement(parent, tag)
        if text:
            elem.text = text
        return elem

    def __exit__(self, exception_type, value, traceback):
        AssessmentSummary._add(self._root, 'end-ts', utillib.posix_epoch())

        tree = ET.ElementTree(self._root)
        tree.write(self._filename, encoding='UTF-8', xml_declaration=True)

    def add_report(self, build_artifact_id, cmd, exit_code,
                   environ, cwd, report, stdout,
                   stderr, starttime, endtime):

        assess_elem = AssessmentSummary._add(self._assessment_artifacts, 'assessment')
        if build_artifact_id:
            AssessmentSummary._add(assess_elem, 'build-artifact-id',
                                   str(build_artifact_id) if isinstance(build_artifact_id, int)
                                   else build_artifact_id)
        if osp.isfile(report):
            AssessmentSummary._add(assess_elem, 'report', osp.basename(report))
        if osp.isfile(stdout):
            AssessmentSummary._add(assess_elem, 'stdout', osp.basename(stdout))
        if osp.isfile(stderr):
            AssessmentSummary._add(assess_elem, 'stderr', osp.basename(stderr))
        AssessmentSummary._add(assess_elem, 'exit-code', str(exit_code))
        AssessmentSummary._add(assess_elem, 'start-ts', starttime)
        AssessmentSummary._add(assess_elem, 'end-ts', endtime)

        cmd_elem = AssessmentSummary._add(assess_elem, 'command')

        AssessmentSummary._add(cmd_elem, 'cwd', cwd)
        env_elem = AssessmentSummary._add(cmd_elem, 'environment')
        for key in environ.keys():
            AssessmentSummary._add(env_elem, 'env', '{0}={1}'.format(key, environ[key]))

        AssessmentSummary._add(cmd_elem, 'executable', cmd[0])
        args_elem = AssessmentSummary._add(cmd_elem, 'args')
        for arg in cmd[1:]:
            AssessmentSummary._add(args_elem, 'arg', arg)


class SwaTool:

    TOOL_DOT_CONF = 'tool.conf'

    def __init__(self, input_root_dir, tool_root_dir):

        tool_conf_file = osp.join(input_root_dir, SwaTool.TOOL_DOT_CONF)
        self.tool_root_dir = tool_root_dir
        self.input_root_dir = input_root_dir

        tool_conf = confreader.read_conf_into_dict(tool_conf_file)

        if 'tool-defaults' in tool_conf:
            tool_defaults_file = osp.join(input_root_dir, tool_conf['tool-defaults'])
            self._tool_conf = confreader.read_conf_into_dict(tool_defaults_file)
            self._tool_conf.update(tool_conf)
        else:
            self._tool_conf = tool_conf

        self._tool_conf = {key: utillib.expandvar(self._tool_conf[key], self._tool_conf)
                           for key in self._tool_conf}

        if 'assessment-report-template' not in self._tool_conf:
            self._tool_conf['assessment-report-template'] = 'assessment_report{0}.xml'

        self._unarchive(input_root_dir, tool_root_dir)
        self._install(tool_root_dir)

        # logging.info('TOOL CONF: %s', self._tool_conf)

    def _unarchive(self, input_root_dir, tool_root_dir):

        with LogTaskStatus('tool-unarchive'):
            tool_archive = osp.join(input_root_dir, self._tool_conf['tool-archive'])
            exit_code = utillib.unpack_archive(tool_archive, tool_root_dir)

            if exit_code != 0:
                raise UnpackArchiveError(self._tool_conf['tool-archive'])

    def _get_env(self):
        new_env = dict(os.environ)

        if 'tool-env' in self._tool_conf:
            tool_env = self._tool_conf['tool-env']
            # new_env.update({a[0] : a[2] for a in \
            #                 map(lambda s: s.partition('='), tool_env.split(','))})
            new_env.update(((var_val.partition('=')[0], var_val.partition('=')[2])
                            for var_val in tool_env.split(',')))
        return new_env

    def _install(self, tool_root_dir):

        with LogTaskStatus('tool-install') as status_dot_out:

            if 'tool-install-cmd' not in self._tool_conf:
                self._tool_conf['executable'] = osp.normpath(osp.join(osp.join(tool_root_dir,
                                                                               self._tool_conf['tool-dir']),
                                                                      self._tool_conf['executable']))

                status_dot_out.skip_task()
            else:

                install_cmd = self._tool_conf['tool-install-cmd']
                logging.info('TOOL INSTALL COMMAND: %s', install_cmd)

                exit_code, environ = utillib.run_cmd(install_cmd,
                                                     cwd=osp.join(tool_root_dir,
                                                                  self._tool_conf['tool-dir']),
                                                     env=self._get_env())
                logging.info('TOOL INSTALL ENVIRON: %s', environ)

                if exit_code != 0:
                    raise ToolInstallFailedError("Install Tool Failed, "
                                                 "Command '{0}' return {1}".format(install_cmd,
                                                                                   exit_code))

    def _validate_exit_code(self, exit_code):
        if 'valid-exit-status' in self._tool_conf:
            regex = re.compile(self._tool_conf['valid-exit-status'])
            return True if(regex.match(str(exit_code))) else False
        else:
            return True if(exit_code == 0) else False

    def assess(self, build_summary_file, results_root_dir):
        raise NotImplementedError


class WebTool(SwaTool):

    # FILE_TYPE = None
    FILE_TYPE = 'srcfile'

    @classmethod
    def _has_no_artifacts(cls, invoke_file, artifacts):
        ''' Each tool works on certain types of files such as html, css, javascript '''
        tokens = gencmd.get_param_list(invoke_file)

        no_artifacts = True
        for file_type in set(tokens).intersection(set(JsPkg.LANG_EXT_MAPPING.keys())):
            if file_type in artifacts and len(artifacts[file_type]):
                found_artifacts = False
                break

        return found_artifacts

    def __init__(self, input_root_dir, tool_root_dir):
        SwaTool.__init__(self, input_root_dir, tool_root_dir)

    def _split_build_artifacts(self, artifacts):
        '''Splits only if required'''

        # returns list of list
        split_required, max_allowed_size = self._split_artifacts_required(artifacts)
        if split_required:
            split_file_lists = list()

            self._split_list(split_file_lists,
                             artifacts[self.FILE_TYPE],
                             max_allowed_size)

            artifacts.pop(self.FILE_TYPE)
            artifacts_list = list()

            id_count = 1
            for filelist in split_file_lists:
                new_artifacts = dict(artifacts)
                new_artifacts[self.FILE_TYPE] = filelist
                new_artifacts['build-artifact-id'] = '{0}-{1}'.format(new_artifacts['id'], str(id_count))
                new_artifacts['assessment-report'] = osp.join(new_artifacts['results-root-dir'],
                                                              self._tool_conf['assessment-report-template'].format(new_artifacts['build-artifact-id']))
                id_count += 1
                artifacts_list.append(new_artifacts)

            return artifacts_list
        else:
            return [artifacts]

    def _split_artifacts_required(self, artifacts):
        '''returns a tuple with key in attribute and an integer corresponding
        to the size '''
        artifacts_local = dict(artifacts)
        get_cmd_size = lambda invoke_file, _dict: \
                       len(' '.join(gencmd.gencmd(invoke_file, _dict)))

        tool_invoke_file = osp.join(self.input_root_dir,
                                    artifacts['tool-invoke'])

        if get_cmd_size(tool_invoke_file, artifacts_local) > utillib.max_cmd_size():
            artifacts_local.pop(self.FILE_TYPE)
            max_allowed_size = utillib.max_cmd_size() - get_cmd_size(tool_invoke_file,
                                                                     artifacts_local)
            return (True, max_allowed_size)
        else:
            return (False, 0)

    def _split_list(self, llist, filelist, max_args_size):
        if len(' '.join(filelist)) > max_args_size:
            self._split_list(llist, filelist[0:int(len(filelist)/2)], max_args_size)
            self._split_list(llist, filelist[int(len(filelist)/2):], max_args_size)
        else:
            llist.append(filelist)

    def _get_build_artifacts(self, build_artifacts_helper, results_root_dir):

        for artifacts in build_artifacts_helper.get_build_artifacts('web-src'):
            artifacts['build-artifact-id'] = artifacts['id']
            artifacts['results-root-dir'] = results_root_dir
            artifacts.update(self._tool_conf)
            artifacts['assessment-report'] = osp.join(artifacts['results-root-dir'],
                                                      artifacts['assessment-report-template'].format(artifacts['build-artifact-id']))

            for new_artifacts in self._split_build_artifacts(artifacts):
                yield new_artifacts

    def _set_tool_config(self, pkg_dir):

        if self._tool_conf.get('tool-config-required', None) == 'true':
            if 'tool-config-file' in self._tool_conf and \
               osp.isfile(osp.join(pkg_dir, self._tool_conf['tool-config-file'])):
                # Make the path absolute
                self._tool_conf['tool-config-file'] = osp.normpath(osp.join(pkg_dir,
                                                                            self._tool_conf['tool-config-file']))
            else:
                self._tool_conf['tool-config-file'] = self._tool_conf['tool-default-config-file']
    
    def assess(self, build_summary_file, results_root_dir):

        if not osp.isdir(results_root_dir):
            os.makedirs(results_root_dir, exist_ok=True)

        assessment_summary_file = osp.join(results_root_dir, 'assessment_summary.xml')
        build_artifacts_helper = BuildArtifactsHelper(build_summary_file)
        self._set_tool_config(build_artifacts_helper.get_pkg_dir())
        logging.info('TOOL CONF: %s', self._tool_conf)

        passed = 0
        failed = 0
        with AssessmentSummary(assessment_summary_file,
                               build_artifacts_helper,
                               self._tool_conf) as assessment_summary:

            for artifacts in self._get_build_artifacts(build_artifacts_helper,
                                                       results_root_dir):

                if 'report-on-stdout' in artifacts \
                   and artifacts['report-on-stdout'] == 'true':
                    outfile = artifacts['assessment-report']
                else:
                    outfile = osp.join(results_root_dir,
                                       'swa_tool_stdout{0}.out'.format(artifacts['build-artifact-id']))

                errfile = osp.join(results_root_dir,
                                   'swa_tool_stderr{0}.out'.format(artifacts['build-artifact-id']))

                invoke_file = osp.join(self.input_root_dir, artifacts['tool-invoke'])
                skip_assess = WebTool._has_no_artifacts(invoke_file, artifacts)
                
                start_time = utillib.posix_epoch()

                # SKIP Assessment if no artifacts relavent to the tools are found
                if not skip_assess:
                    assess_cmd = gencmd.gencmd(invoke_file, artifacts)
                    logging.info('ASSESSMENT CMD: %s', assess_cmd)

                    exit_code, environ = utillib.run_cmd(assess_cmd,
                                                         outfile=outfile,
                                                         errfile=errfile,
                                                         cwd=results_root_dir,
                                                         env=self._get_env())

                    logging.info('ASSESSMENT WORKING DIR: %s', results_root_dir)
                    logging.info('ASSESSMENT EXIT CODE: %d', exit_code)
                    logging.info('ASSESSMENT ENVIRONMENT: %s', environ)
                else:
                    assess_cmd, exit_code, environ = [None], 0, self._get_env()

                assessment_report = artifacts['assessment-report'] \
                                    if outfile != artifacts['assessment-report'] else outfile
                
                # write assessment summary file
                # return pass, fail, assessment_summary
                assessment_summary.add_report(artifacts['build-artifact-id'],
                                              assess_cmd,
                                              exit_code,
                                              environ,
                                              results_root_dir,
                                              assessment_report,
                                              outfile,
                                              errfile,
                                              start_time,
                                              utillib.posix_epoch())

                if not skip_assess:
                    if self._validate_exit_code(exit_code):
                        passed += 1
                    else:
                        failed += 1

            return (passed, failed, assessment_summary_file)


class JsTool(WebTool):

    FILE_TYPE = 'javascript'

    def __init__(self, input_root_dir, tool_root_dir):
        WebTool.__init__(self, input_root_dir, tool_root_dir)


class PhpTool(WebTool):

    FILE_TYPE = 'php'

    def __init__(self, input_root_dir, tool_root_dir):
        WebTool.__init__(self, input_root_dir, tool_root_dir)


class Flow(SwaTool):

    def __init__(self, input_root_dir, tool_root_dir):
        SwaTool.__init__(self, input_root_dir, tool_root_dir)

    @classmethod
    def _convert_to_regex(cls, pattern):
        regex = fnmatch.translate(pattern)
        # fnmatch adds this to the end of the regex, don't understand why
        if regex.endswith('\\Z(?ms)'):
            regex = regex.rpartition('\\Z(?ms)')[0]

        return regex

    def _create_flowconfig(self, assessment_working_dir):

        if not osp.isfile(osp.join(assessment_working_dir, '.flowconfig')):

            content = '''[include]\n\n[libs]\n\n[options]\n\n[ignore]\n<PROJECT_ROOT>/node_modules\n'''
            if self.build_artifacts_helper['package-exclude-paths']:
                # TODO: These may have to converted into ocaml regex
                ignore_patterns = '\n'.join({'<PROJECT_ROOT>/' + self._convert_to_regex(pattern.strip()) for pattern in \
                                     self.build_artifacts_helper['package-exclude-paths'].split(',')})
                content += ignore_patterns + '\n'

            ignore_file = None
            if osp.isfile(osp.join(assessment_working_dir, '.npmignore')):
                ignore_file = osp.join(assessment_working_dir, '.npmignore')
            elif osp.isfile(osp.join(assessment_working_dir, '.gitignore')):
                ignore_file = osp.join(assessment_working_dir, '.gitignore')

            if ignore_file:
                with open(ignore_file) as fobj:
                    ignore_patterns = {p.strip().strip('\n') for p in fobj
                                       if p and not p.isspace() and not p.strip().startswith('#')}
                    content += '\n'.join({'<PROJECT_ROOT>/' + self._convert_to_regex(pattern)
                                          for pattern in ignore_patterns})
                    content += '\n'

            with open(osp.join(assessment_working_dir, '.flowconfig'), 'w') as fobj:
                logging.info('DOT FLOWCONFIG: %s', content)
                fobj.write(content)

    def assess(self, build_summary_file, results_root_dir):

        if not osp.isdir(results_root_dir):
            os.makedirs(results_root_dir, exist_ok=True)

        assessment_summary_file = osp.join(results_root_dir, 'assessment_summary.xml')

        self.build_artifacts_helper = BuildArtifactsHelper(build_summary_file)

        passed = 0
        failed = 0
        with AssessmentSummary(assessment_summary_file,
                               self.build_artifacts_helper,
                               self._tool_conf) as assessment_summary:

            artifacts = {'id': 1}

            artifacts.update(self._tool_conf)
            assessment_report = osp.join(results_root_dir,
                                         artifacts['assessment-report-template'].format(artifacts['id']))

            if 'report-on-stdout' in artifacts \
               and artifacts['report-on-stdout'] == 'true':
                outfile = assessment_report
            else:
                artifacts['assessment-report'] = assessment_report
                outfile = osp.join(results_root_dir,
                                   'swa_tool_stdout{0}.out'.format(artifacts['id']))

            errfile = osp.join(results_root_dir,
                               'swa_tool_stderr{0}.out'.format(artifacts['id']))

            assess_cmd = gencmd.gencmd(osp.join(self.input_root_dir,
                                                artifacts['tool-invoke']),
                                       artifacts)

            logging.info('ASSESSMENT CMD: %s', assess_cmd)

            # For Flow package dir is assessment working dir
            assessment_working_dir = self.build_artifacts_helper.get_pkg_dir()

            start_time = utillib.posix_epoch()

            # TODO: create flow config
            self._create_flowconfig(assessment_working_dir)

            exit_code, environ = utillib.run_cmd(assess_cmd,
                                                 outfile=outfile,
                                                 errfile=errfile,
                                                 cwd=assessment_working_dir,
                                                 env=self._get_env())

            logging.info('ASSESSMENT WORKING DIR: %s', assessment_working_dir)
            logging.info('ASSESSMENT EXIT CODE: %d', exit_code)
            logging.info('ASSESSMENT ENVIRONMENT: %s', environ)

            # write assessment summary file
            # return pass, fail, assessment_summary
            assessment_summary.add_report(artifacts['id'],
                                          assess_cmd,
                                          exit_code,
                                          environ,
                                          assessment_working_dir,
                                          assessment_report,
                                          outfile,
                                          errfile,
                                          start_time,
                                          utillib.posix_epoch())

            if self._validate_exit_code(exit_code):
                passed += 1
            else:
                failed += 1

        return (passed, failed, assessment_summary_file)


def assess(input_root_dir, output_root_dir, tool_root_dir,
           results_root_dir, build_summary_file):

    tool_conf_file = osp.join(input_root_dir, SwaTool.TOOL_DOT_CONF)
    tool_conf = confreader.read_conf_into_dict(tool_conf_file)

    if tool_conf['tool-type'] == 'flow':
        swatool = Flow(input_root_dir, tool_root_dir)
    elif tool_conf['tool-type'] in ['php_codesniffer', 'phpmd']:
        swatool = PhpTool(input_root_dir, tool_root_dir)
    elif tool_conf['tool-type'] in ['cloc', 'lizard']:
        swatool = WebTool(input_root_dir, tool_root_dir)
    else:
        swatool = JsTool(input_root_dir, tool_root_dir)

    try:
        with LogTaskStatus('assess') as status_dot_out:

            (passed, failed,
             assessment_summary_file) = swatool.assess(build_summary_file, results_root_dir)

            if passed == 0 and failed == 0:
                exit_code = 0
                status_dot_out.skip_task(task_msg=None,
                                         task_msg_indetail="No relavent files found to run '%s'" % tool_conf['tool-type'])
            else:
                exit_code = 1 if(failed) else 0
                status_dot_out.update_task_status(exit_code,
                                                  'pass: {0}, fail: {1}'.format(passed, failed))
    except (BuildArtifactsError,
            BuildSummaryError) as err:
        logging.exception(err)
        exit_code = 1
        assessment_summary_file = None

    finally:
        results_conf = dict()
        results_conf['exit-code'] = str(exit_code)

        if assessment_summary_file and osp.isfile(assessment_summary_file):
            results_conf['assessment-summary-file'] = osp.basename(assessment_summary_file)

            with LogTaskStatus('results-archive'):
                results_archive = shutil.make_archive(osp.join(output_root_dir, 'results'),
                                                      'gztar',
                                                      osp.dirname(results_root_dir),
                                                      osp.basename(results_root_dir))

                results_conf['results-archive'] = osp.basename(results_archive)
                results_conf['results-dir'] = osp.basename(results_root_dir)

                utillib.write_to_file(osp.join(output_root_dir, 'results.conf'),
                                      results_conf)

    return (exit_code, assessment_summary_file)

