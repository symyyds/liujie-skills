#!/usr/bin/env python3
"""Audit registered evidence structure; never certify scientific truth."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

CORE = {'scope', 'experiment_plan', 'data_audit', 'experiment_results',
        'baseline_table', 'baseline_source_data', 'manuscript_source',
        'manuscript_pdf', 'integrity_report', 'delivery_index', 'reproduction_instructions'}
DIAGRAMS = {'diagram_placeholder', 'pipeline_placeholder', 'backbone_placeholder'}
TABLES = ('artifacts', 'papers', 'datasets', 'experiments', 'runs', 'metrics',
          'baseline_values', 'claims', 'issues')


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


class Auditor:
    def __init__(self, data, root, final):
        self.d, self.root, self.final = data, root, final
        self.errors, self.warnings, self.t = [], [], {}

    def error(self, message):
        self.errors.append(message)

    def gap(self, message):
        (self.errors if self.final else self.warnings).append(message)

    def text(self, value, label):
        if not isinstance(value, str):
            self.error(label + ': expected string')
            return False
        if not value.strip():
            self.gap(label + ': missing')
            return False
        return True

    def obj(self, key):
        value = self.d.get(key)
        if not isinstance(value, dict):
            self.error(key + ': expected object')
            return {}
        return value

    def refs(self, ids, table, label, required=False):
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
            self.error(label + ': expected array of ids')
            return []
        if required and not ids:
            self.gap(label + ': missing ids')
        for ident in ids:
            if ident not in self.t[table]:
                self.error(label + ': unknown ' + table + ' id ' + ident)
        return [x for x in ids if x in self.t[table]]

    def artifact(self, ident, label, role=None):
        if not isinstance(ident, str) or not ident:
            self.gap(label + ': missing artifact id')
            return
        row = self.t['artifacts'].get(ident)
        if row is None:
            self.error(label + ': unknown artifact ' + ident)
        elif role and row.get('role') != role:
            self.error(label + ': incorrect artifact role')

    def run(self):
        if type(self.d.get('schema_version')) is not int or self.d['schema_version'] != 1:
            self.error('schema_version must be integer 1')
        project, scope, phase = self.obj('project'), self.obj('scope'), self.obj('phase_state')
        full, empirical = scope.get('deliverable') == 'full_paper', project.get('kind') == 'empirical'
        if project.get('kind') not in ('empirical', 'theoretical', 'review'):
            self.error('invalid project.kind')
        if scope.get('deliverable') not in ('full_paper', 'partial'):
            self.error('invalid scope.deliverable')
        for field in ('title', 'target_venue', 'submission_cycle'):
            self.text(project.get(field, ''), 'project.' + field)
        self.text(scope.get('approval_quote', ''), 'scope.approval_quote')
        if phase.get('current') not in ['S' + str(i) for i in range(8)]:
            self.error('invalid current phase')
        if phase.get('status') not in ('awaiting_start', 'in_progress', 'awaiting_acceptance', 'accepted', 'blocked', 'skipped'):
            self.error('invalid phase status')
        history = phase.get('history', [])
        if not isinstance(history, list):
            self.error('phase history must be array')
        else:
            for event in history:
                if not isinstance(event, dict):
                    self.error('phase history must contain objects')
                elif event.get('event') in ('start_approved', 'accepted'):
                    self.text(event.get('user_quote', ''), 'phase history user_quote')

        for name in TABLES:
            records = self.d.get(name)
            self.t[name] = {}
            if not isinstance(records, list):
                self.error(name + ': expected array')
                continue
            for row in records:
                if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip():
                    self.error(name + ': record needs string id')
                    continue
                if row['id'] in self.t[name]:
                    self.error(name + ': duplicate id ' + row['id'])
                self.t[name][row['id']] = row
        t = self.t
        accepted = self.refs(scope.get('accepted_placeholders', []), 'artifacts', 'accepted_placeholders')
        roles = set()
        for ident, row in t['artifacts'].items():
            label = 'artifact ' + ident
            role = row.get('role', '')
            self.text(role, label + '.role')
            if row.get('status') == 'placeholder':
                if ident not in accepted or role not in DIAGRAMS:
                    self.gap(label + ': unapproved or non-diagram placeholder')
                else:
                    self.warnings.append(label + ': approved diagram awaiting replacement')
            elif row.get('status') == 'present':
                if isinstance(role, str):
                    roles.add(role)
            else:
                self.error(label + ': invalid status')
            if not self.text(row.get('path', ''), label + '.path'):
                continue
            path = Path(row['path'])
            path = path if path.is_absolute() else self.root / path
            try:
                if not path.is_file():
                    self.gap(label + ': file missing ' + str(path))
                    continue
                if not path.stat().st_size:
                    self.gap(label + ': empty evidence file')
                sha = row.get('sha256', '')
                if not sha:
                    self.gap(label + ': sha256 missing')
                elif not isinstance(sha, str) or not re.fullmatch('[0-9a-fA-F]{64}', sha):
                    self.error(label + ': invalid sha256')
                elif file_hash(path) != sha.lower():
                    self.error(label + ': sha256 mismatch')
            except OSError as exc:
                self.error(label + ': unreadable: ' + str(exc))
        required = scope.get('required_roles', [])
        if not isinstance(required, list) or any(not isinstance(x, str) for x in required):
            self.error('required_roles must be string array')
            required = []
        required = set(required)
        selected = scope.get('selected_phases', [])
        if not isinstance(selected, list) or any(x not in ['S' + str(i) for i in range(8)] for x in selected):
            self.error('selected_phases must be phase array')
            selected = []
        if full and empirical:
            required |= CORE
            if 'S1' in selected:
                required |= {'corpus_inventory', 'figure_gallery'}
        if not required:
            self.gap('no explicit required artifact roles')
        for role in sorted(required - roles):
            self.gap('required artifact role missing: ' + role)

        for ident, row in t['datasets'].items():
            self.refs(row.get('artifact_ids', []), 'artifacts', 'dataset ' + ident, True)
            status = row.get('audit_status')
            if status not in ('passed', 'conditional', 'failed', 'pending'):
                self.error('dataset ' + ident + ': invalid audit status')
            elif status in ('failed', 'pending'):
                self.gap('dataset ' + ident + ': audit incomplete or failed')
            elif status == 'conditional':
                for field in ('limitations', 'approval_quote'):
                    self.text(row.get(field, ''), 'dataset ' + ident + '.' + field)
        required_exp = self.refs(scope.get('required_experiment_ids', []), 'experiments', 'required_experiment_ids', full and empirical)
        for ident, row in t['experiments'].items():
            status = row.get('status')
            if status not in ('succeeded', 'failed', 'blocked', 'not_run', 'excluded'):
                self.error('experiment ' + ident + ': invalid status')
            deps = self.refs(row.get('dependency_ids', []), 'experiments', 'experiment ' + ident + ' dependencies')
            if ident in deps:
                self.error('experiment ' + ident + ': self dependency')
            runs = self.refs(row.get('run_ids', []), 'runs', 'experiment ' + ident + ' runs', status == 'succeeded')
            good = False
            for run_id in runs:
                run = t['runs'][run_id]
                if run.get('experiment_id') != ident:
                    self.error('experiment ' + ident + ': run ownership mismatch')
                good |= run.get('status') == 'succeeded'
            if status == 'succeeded' and not good:
                self.gap('experiment ' + ident + ': no successful run')
            if status == 'excluded':
                for field in ('exclusion_reason', 'approval_quote'):
                    self.text(row.get(field, ''), 'experiment ' + ident + '.' + field)
            elif ident in required_exp and status != 'succeeded':
                self.gap('required experiment ' + ident + ': incomplete')
        for ident, row in t['runs'].items():
            self.refs([row.get('experiment_id')], 'experiments', 'run ' + ident + ' experiment')
            status = row.get('status')
            if status not in ('succeeded', 'failed', 'running'):
                self.error('run ' + ident + ': invalid status')
            if status == 'running':
                self.gap('run ' + ident + ': still running')
            self.refs(row.get('dataset_ids', []), 'datasets', 'run ' + ident + ' datasets')
            for field in ('code_artifact_id', 'config_artifact_id', 'log_artifact_id'):
                self.artifact(row.get(field), 'run ' + ident + '.' + field)
            self.refs(row.get('result_artifact_ids', []), 'artifacts', 'run ' + ident + ' results', status == 'succeeded')
            if status == 'succeeded':
                for field in ('started_at', 'ended_at'):
                    self.text(row.get(field, ''), 'run ' + ident + '.' + field)

        required_metrics = self.refs(scope.get('required_metric_ids', []), 'metrics', 'required_metric_ids', full and empirical)
        for ident, row in t['metrics'].items():
            for field in ('name', 'unit'):
                self.text(row.get(field, ''), 'metric ' + ident + '.' + field)
            if row.get('direction') not in ('min', 'max'):
                self.error('metric ' + ident + ': direction must be min or max')
        groups = {}
        for ident, row in t['baseline_values'].items():
            label = 'baseline ' + ident
            metric_id, paper_id, source = row.get('metric_id'), row.get('paper_id'), row.get('source_kind')
            self.refs([metric_id], 'metrics', label + ' metric')
            if source not in ('reported', 'reproduced', 'ours', 'estimated_from_figure'):
                self.error(label + ': invalid source_kind')
            if (paper_id == 'ours') != (source == 'ours'):
                self.error(label + ': ours/source_kind mismatch')
            if paper_id != 'ours':
                valid = self.refs([paper_id], 'papers', label + ' paper')
                for paper in valid:
                    for field in ('title', 'venue', 'doi_or_url'):
                        self.text(t['papers'][paper].get(field, ''), label + ' paper.' + field)
            if isinstance(metric_id, str) and metric_id in t['metrics'] and row.get('unit') != t['metrics'][metric_id].get('unit'):
                self.error(label + ': unit mismatch')
            for field in ('comparison_group', 'unit', 'protocol'):
                self.text(row.get(field, ''), label + '.' + field)
            if type(row.get('comparable')) is not bool:
                self.error(label + ': comparable must be boolean')
            value = row.get('value')
            if value is None:
                self.text(row.get('missing_reason', ''), label + '.missing_reason')
                continue
            if type(value) not in (int, float) or not math.isfinite(value):
                self.error(label + ': value must be finite number, not boolean')
                continue
            self.refs(row.get('source_artifact_ids', []), 'artifacts', label + ' sources', True)
            if source in ('reported', 'estimated_from_figure'):
                self.text(row.get('source_locator', ''), label + '.source_locator')
            if source == 'estimated_from_figure':
                self.text(row.get('approval_quote', ''), label + '.approval_quote')
            run_ids = self.refs(row.get('run_ids', []), 'runs', label + ' runs', source in ('ours', 'reproduced'))
            for run_id in run_ids:
                if t['runs'][run_id].get('status') != 'succeeded':
                    self.error(label + ': numeric result uses unsuccessful run')
            fields = ('metric_id', 'comparison_group', 'protocol', 'unit')
            if row.get('comparable') is True and all(isinstance(row.get(k), str) for k in fields):
                key = tuple(row[k] for k in fields)
                groups.setdefault(key, set()).add('ours' if paper_id == 'ours' else 'external')
        paired = {key[0] for key, parties in groups.items() if {'ours', 'external'} <= parties}
        if full and empirical:
            for metric in required_metrics:
                if metric not in paired:
                    self.gap('metric ' + metric + ': no comparable numeric baseline/Ours pair')
            table = self.obj('baseline_table')
            self.artifact(table.get('artifact_id'), 'baseline_table.artifact_id', 'baseline_table')
            self.artifact(table.get('source_data_artifact_id'), 'baseline_table.source_data_artifact_id', 'baseline_source_data')
            self.text(table.get('manuscript_locator', ''), 'baseline_table.manuscript_locator')
            if table.get('verified_in_manuscript') is not True:
                self.gap('baseline table not verified inside manuscript')
        if full and not t['claims']:
            self.gap('full paper has no registered claims')
        for ident, row in t['claims'].items():
            self.text(row.get('text', ''), 'claim ' + ident + '.text')
            self.refs(row.get('evidence_artifact_ids', []), 'artifacts', 'claim ' + ident, True)
            if row.get('verified') is not True:
                self.gap('claim ' + ident + ': not verified')
        for ident, row in t['issues'].items():
            severity, status = row.get('severity'), row.get('status')
            if severity not in ('blocking', 'major', 'minor') or status not in ('open', 'resolved', 'accepted'):
                self.error('issue ' + ident + ': invalid status or severity')
            elif status != 'resolved' and severity in ('blocking', 'major'):
                self.gap('issue ' + ident + ': unresolved ' + severity)
            elif status == 'open':
                self.warnings.append('issue ' + ident + ': open minor limitation')
            if status == 'accepted':
                self.text(row.get('approval_quote', ''), 'issue ' + ident + '.approval_quote')
            elif status == 'resolved':
                self.text(row.get('resolution', ''), 'issue ' + ident + '.resolution')
        return {'mode': 'final' if self.final else 'draft', 'passed': not self.errors,
                'errors': self.errors, 'warnings': self.warnings,
                'summary': {k: len(v) for k, v in t.items()},
                'limitation': 'Structure only; not proof of truth, fairness, authentic approval, or manuscript correctness.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--mode', choices=('draft', 'final'), default='draft')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict):
            raise ValueError('Manifest must be JSON object')
        root = args.manifest.resolve().parent
        result = Auditor(data, root, args.mode == 'final').run()
        output = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.report:
            protected = {args.manifest.resolve()}
            for row in data.get('artifacts', []):
                if isinstance(row, dict) and isinstance(row.get('path'), str):
                    p = Path(row['path'])
                    protected.add((p if p.is_absolute() else root / p).resolve())
            if args.report.resolve() in protected:
                raise ValueError('Report must not overwrite manifest or registered evidence')
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output + '\n', encoding='utf-8')
        print(output)
        return 1 if result['errors'] else 0
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
