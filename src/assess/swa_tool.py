import os
import os.path as osp
import logging

from .helper import BuildArtifactsHelper
from .assessment_summary import AssessmentSummary

from .. import gencmd
from .. import utillib
from .. import confreader
from ..logger import LogTaskStatus
from ..utillib import UnpackArchiveError
from ..build.common import LANG_EXT_MAPPING


class ToolInstallFailedError(Exception):

    def __init__(self, value):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return repr(self.value)


class SwaToolBase:

    TOOL_DOT_CONF = 'tool.conf'

    def __init__(self, input_root_dir, tool_root_dir):

        tool_conf_file = osp.join(input_root_dir, SwaToolBase.TOOL_DOT_CONF)
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

                exit_code, environ = utillib.run_cmd(install_cmd,
                                                     cwd=osp.join(tool_root_dir,
                                                                  self._tool_conf['tool-dir']),
                                                     env=self._get_env(),
                                                     description='TOOL INSTALL')

                if exit_code != 0:
                    raise ToolInstallFailedError("Install Tool Failed, "
                                                 "Command '{0}' return {1}".format(install_cmd,
                                                                                   exit_code))
                               
    def _validate_exit_code(self, exit_code):
        if 'valid-exit-status' in self._tool_conf:
            valid_exit_codes = [int(ec.strip())
                                for ec in self._tool_conf['valid-exit-status'].split(',')
                                if ec.strip()]

            return exit_code in valid_exit_codes
        else:
            return True if(exit_code == 0) else False

    def assess(self, build_summary_file, results_root_dir):
        raise NotImplementedError


class SwaTool(SwaToolBase):

    # FILE_TYPE = None
    FILE_TYPE = 'srcfile'

    @classmethod
    def _tool_target_artifacts(cls, invoke_file):
        ''' Each tool works on certain types of files such as html, css, javascript.
        This method takes the invoke_file for the tool and return that target 
        artifacts the tools works on'''

        all_lang = set(LANG_EXT_MAPPING.keys())
        all_lang.add(SwaTool.FILE_TYPE)  # to add 'srcfile'
        tokens = gencmd.get_param_list(invoke_file)
        return list(set(tokens).intersection(all_lang))

    @classmethod
    def _has_no_artifacts(cls, invoke_file, artifacts):
        ''' Each tool works on certain types of files such as html, css, javascript.
        This method takes the invoke_file for the tool and checks if artifacts 
        required by the tool are present in the package'''

        return not any(True if file_type in artifacts and artifacts[file_type] else False
                       for file_type in cls._tool_target_artifacts(invoke_file))

    @classmethod
    def _split_artifacts_required(cls, tool_invoke_file, artifacts):
        '''returns a tuple with key in attribute and an integer corresponding
        to the size '''

        def get_cmd_size(invoke_file, _dict):
            return len(' '.join(gencmd.gencmd(invoke_file, _dict)))

        artifacts_local = dict(artifacts)

        if get_cmd_size(tool_invoke_file, artifacts_local) > utillib.max_cmd_size():

            # Remove all the artifacts that the tool works on, and then check the size
            for k in SwaTool._tool_target_artifacts(tool_invoke_file):
                if k in artifacts_local and artifacts_local[k]:
                    artifacts_local.pop(k)

            max_allowed_size = utillib.max_cmd_size() - get_cmd_size(tool_invoke_file,
                                                                     artifacts_local)
            return (True, max_allowed_size)
        else:
            return (False, 0)

    @classmethod
    def _split_list(cls, filelist, max_args_size):

        def split(llist, filelist, max_args_size):
            if len(' '.join(filelist)) > max_args_size:
                split(llist, filelist[0:int(len(filelist) / 2)], max_args_size)
                split(llist, filelist[int(len(filelist) / 2):], max_args_size)
            else:
                llist.append(filelist)

        list_of_lists = list()
        split(list_of_lists, filelist, max_args_size)
        return list_of_lists

    def __init__(self, input_root_dir, tool_root_dir):
        SwaToolBase.__init__(self, input_root_dir, tool_root_dir)

    def _split_build_artifacts(self, artifacts):
        '''Splits only if required'''

        tool_invoke_file = osp.join(self.input_root_dir,
                                    artifacts['tool-invoke'])

        (split_required,
         max_allowed_size) = SwaTool._split_artifacts_required(tool_invoke_file,
                                                               artifacts)
        if split_required:
            tool_target_artifacts = SwaTool._tool_target_artifacts(tool_invoke_file)
            package_artifacts = {k: v for k, v in artifacts.items()
                                   if k in tool_target_artifacts and artifacts[k]}
            # Remove tool_target_artifacts from the dictionary, split and add them later
            [None for m in map(artifacts.pop, package_artifacts.keys())]

            id_count = 1
            for file_type in package_artifacts.keys():
                for filelist in SwaTool._split_list(package_artifacts[file_type], max_allowed_size):
                    new_artifacts = dict(artifacts)
                    new_artifacts[file_type] = filelist
                    new_artifacts['build-artifact-id'] = '{0}-{1}'.format(new_artifacts['id'],
                                                                          str(id_count))
                    new_artifacts['assessment-report'] = osp.join(new_artifacts['results-root-dir'],
                                                                  self._tool_conf['assessment-report-template'].format(new_artifacts['build-artifact-id']))
                    id_count += 1
                    yield new_artifacts
        else:
            yield artifacts

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
                skip_assess = SwaTool._has_no_artifacts(invoke_file, artifacts)

                # SKIP Assessment if there are no artifacts relavent to the tool
                if not skip_assess:
                    start_time = utillib.posix_epoch()
                    assess_cmd = gencmd.gencmd(invoke_file, artifacts)

                    exit_code, environ = utillib.run_cmd(assess_cmd,
                                                         outfile=outfile,
                                                         errfile=errfile,
                                                         cwd=results_root_dir,
                                                         env=self._get_env(),
                                                         description='ASSESSMENT')

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
                    if self._validate_exit_code(exit_code):
                        passed += 1
                    else:
                        failed += 1
                else:
                    logging.info('ASSESSMENT SKIP (NO SOURCE FILES FOUND)')

            return (passed, failed, assessment_summary_file)

