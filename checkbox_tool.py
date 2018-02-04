import re
import sys
from collections import namedtuple
from plainbox.abc import IJobQualifier
from plainbox.impl.session.assistant import SessionAssistant
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.template import TemplateUnit


UnitProxy = namedtuple('UnitProxy', ['id', 'kind', 'extras', 'annotations'])

def template_to_re(uid):
    uid = uid.replace('{__index__}', r'\d+')
    greedy = re.sub(r'\{.+\}', '.+', uid)
    nongreedy = re.sub(r'\{.+?\}', '.+?', uid)
    return nongreedy, greedy

class CheckboxTool:
    def __init__(self):
        self.sa = SessionAssistant('CheckboxTool')

        self.sa.select_providers('*')
        self.sa.start_new_session('print_sequence')
        self.all_tps = self.sa.get_test_plans()

        self.units = dict()
        self.template_units = dict()
        for unit in self.sa._context._unit_list:
            u_type = type(unit)
            if u_type == TemplateUnit:
                unit.re_matcher, unit.re_greedy = template_to_re(unit.id)
                self.template_units[unit.id] = unit
            if not (issubclass(u_type, JobDefinition)):
                continue
            self.units[unit.id] = unit

    def get_kind_for_unit(self, line, qualifier_unit):
        kind = 'unknown'
        extras = ''
        full_id = line
        if "::" not in full_id:
            qid = qualifier_unit.qualify_id(full_id)
            full_id = qid
        if '::after-suspend' in full_id:
            full_id = full_id.replace('::after-suspend-', '::')
            extras = '  <= {} REMOVED "after-suspend-" PREFIX'.format(full_id)
                
        if full_id in self.units.keys():
            plugin = self.units[full_id].plugin
            if plugin in ['shell', 'resource', 'attachment']:
                kind = 'automatic'
            else:
                kind = 'manual'
            if self.units[full_id].depends:
                for dep_id in self.units[full_id].depends.split():
                    dep_kind, _ = self.get_kind_for_unit(dep_id, self.units[full_id]) 
                    if dep_kind == 'manual':
                        if kind == 'automatic':
                            extras = 'manual b/c of dep on {}'.format(
                                    dep_id) + extras
                        kind = 'manual'
        if kind == 'unknown':
            candidates = []
            for tid, tunit in self.template_units.items():
                matches = re.match(tunit.re_matcher, full_id)
                if matches:
                    candidates.append(tunit)
            if not candidates:
                for tid, tunit in self.template_units.items():
                    matches = re.match(tunit.re_greedy, full_id)
                    if matches:
                        candidates.append(tunit)

            tunit = None
            if len(candidates) == 1:
                tunit = candidates[0]
            elif len(candidates) > 1:
                from difflib import SequenceMatcher
                tid = sorted([c.id for c in candidates], key=lambda a: SequenceMatcher(
                    None, a, line).ratio(), reverse=True)[0]
                tunit = self.template_units[tid]

            if tunit:
                if tunit.get_record_value('plugin') in ['shell', 'resource', 'attachment']:
                    kind = 'automatic'
                else:
                    kind = 'manual'
                if tunit.get_record_value('depends'):
                    for dep_id in tunit.get_record_value('depends').split():
                        dep_kind, _ = self.get_kind_for_unit(dep_id, tunit)
                        if dep_kind == 'manual':
                            if kind == 'automatic':
                                extras = 'manual b/c of dep on {}'.format(dep_id) + extras
                            kind = 'manual'
                extras = '   <= {}'.format(tunit.id)
        return kind, extras

    def get_run_sequence(self, tp_id, include_nested = True):
        tp_unit = self.sa.get_test_plan(tp_id)
        result = []
        if include_nested:
            for tp in tp_unit.get_nested_part():
                # print("NESTED {}".format(tp))
                result += self.get_run_sequence(tp.id)
        for line in tp_unit.include.split('\n'):
            if not line:
                continue
                
            if line.startswith('#'):
                continue
            sections = line.split()
            annotations = line[len(sections[0]):]
            line = sections[0]
            line = line.split()[0]
            kind, extras = self.get_kind_for_unit(line, tp_unit)

            result.append(UnitProxy(line, kind, extras, annotations))

        return result
