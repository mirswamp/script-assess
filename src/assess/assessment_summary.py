import os.path as osp
import uuid
import xml.etree.ElementTree as ET

from .. import utillib


class AssessmentSummary:

    def __init__(self,
                 filename,
                 build_artifacts_helper,
                 tool_conf):

        self._filename = filename

	## keep names same as needed
        build_summary_obj = build_artifacts_helper

        self._root = ET.Element('assessment-summary')
        AssessmentSummary._add(self._root, 'assessment-summary-uuid', str(uuid.uuid4()))

        AssessmentSummary._add(self._root, 'build-root-dir',
                               build_artifacts_helper['build-root-dir'])

        AssessmentSummary._add(self._root, 'package-root-dir',
                               osp.join(build_artifacts_helper['build-root-dir'],
                                        build_artifacts_helper['package-root-dir']))

        AssessmentSummary._add(self._root, 'package-name',
                               build_artifacts_helper.get_pkg_conf().get('package-short-name', None))

        AssessmentSummary._add(self._root, 'package-version',
                               build_artifacts_helper.get_pkg_conf().get('package-version', None))
        
        if 'build-summary-uuid' in build_artifacts_helper:
            AssessmentSummary._add(self._root, 'build-summary-uuid',
                                   build_artifacts_helper['build-summary-uuid'])

        if 'build-fw' in build_summary_obj:
            AssessmentSummary._add(self._root, 'assess-fw', build_summary_obj['build-fw'])

        if 'build-fw-version' in build_summary_obj:
            AssessmentSummary._add(self._root, 'assess-fw-version', build_summary_obj['build-fw-version'])


        AssessmentSummary._add(self._root, 'tool-type', tool_conf['tool-type'])
        AssessmentSummary._add(self._root, 'tool-version', tool_conf['tool-version'])
        AssessmentSummary._add(self._root, 'platform-name', utillib.platform())
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
        AssessmentSummary._add(self._root, 'stop-ts', utillib.posix_epoch())

        tree = ET.ElementTree(self._root)
        tree.write(self._filename, encoding='UTF-8', xml_declaration=True)

    def add_non_assessment(self, build_artifact_id, cmd, exit_code,
                           execution_successful, environ, cwd, report, stdout, 
                           stderr, starttime, endtime):
        non_assess_elem = AssessmentSummary._add(self._assessment_artifacts, 'non-assessment')

        if build_artifact_id:
            AssessmentSummary._add(non_assess_elem, 'build-artifact-id',
                                   str(build_artifact_id) if isinstance(build_artifact_id, int)
                                   else build_artifact_id)
        if osp.isfile(stdout):
            AssessmentSummary._add(non_assess_elem, 'stdout', osp.basename(stdout))
        if osp.isfile(stderr):
            AssessmentSummary._add(non_assess_elem, 'stderr', osp.basename(stderr))
        AssessmentSummary._add(non_assess_elem, 'exit-code', str(exit_code))
        AssessmentSummary._add(non_assess_elem, 'execution-successful',
                utillib.bool_to_string(execution_successful))
        AssessmentSummary._add(non_assess_elem, 'start-ts', starttime)
        AssessmentSummary._add(non_assess_elem, 'stop-ts', endtime)

        cmd_elem = AssessmentSummary._add(non_assess_elem, 'command')

        AssessmentSummary._add(cmd_elem, 'cwd', cwd)
        env_elem = AssessmentSummary._add(cmd_elem, 'environment')
        for key in environ.keys():
            AssessmentSummary._add(env_elem, 'env', '{0}={1}'.format(key, environ[key]))

        AssessmentSummary._add(cmd_elem, 'executable', cmd[0])
        args_elem = AssessmentSummary._add(cmd_elem, 'args')
        for arg in cmd:
            AssessmentSummary._add(args_elem, 'arg', arg)

    def add_report(self, build_artifact_id, cmd, exit_code,
                   execution_successful, environ, cwd, report, stdout,
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
        AssessmentSummary._add(assess_elem, 'execution-successful',
                utillib.bool_to_string(execution_successful))
        AssessmentSummary._add(assess_elem, 'start-ts', starttime)
        AssessmentSummary._add(assess_elem, 'stop-ts', endtime)

        cmd_elem = AssessmentSummary._add(assess_elem, 'command')

        AssessmentSummary._add(cmd_elem, 'cwd', cwd)
        env_elem = AssessmentSummary._add(cmd_elem, 'environment')
        for key in environ.keys():
            AssessmentSummary._add(env_elem, 'env', '{0}={1}'.format(key, environ[key]))

        AssessmentSummary._add(cmd_elem, 'executable', cmd[0])
        args_elem = AssessmentSummary._add(cmd_elem, 'args')
        for arg in cmd:
            AssessmentSummary._add(args_elem, 'arg', arg)
