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
