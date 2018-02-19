import os
import re
import shutil
import sys
from collections import namedtuple
from plainbox.abc import IJobQualifier
from plainbox.impl.session.assistant import SessionAssistant
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.template import TemplateUnit
from plainbox.impl.unit.testplan import TestPlanUnit


UnitProxy = namedtuple('UnitProxy', ['id', 'kind', 'extras', 'annotations'])

def template_to_re(uid):
    uid = uid.replace('{__index__}', r'\d+')
    greedy = re.sub(r'\{.+\}', '.+', uid)
    nongreedy = re.sub(r'\{.+?\}', '.+?', uid)
    return nongreedy, greedy

def unqualify_id(tp_unit, uid):
    namespace = tp_unit.qualify_id('')
    if uid.startswith(namespace):
        return  uid.replace(namespace, '')
    else:
        return uid

def generate_tp_unit(tpu):
    write_order = ['id', 'unit', '_name', '_description', 'include',
            'bootstrap_include', 'mandatory_include', 'exclude',
            'nested_part', 'estimated_duration']
    multiline_fields = ['_description', 'include', 'bootstrap_include',
                        'mandatory_include', 'exclude', 'nested_part']

    tp_record = ''
    for field in write_order:
        if field.startswith('_'):
            val = tpu.__getattribute__(field[1:])
        else:
            val = tpu.__getattribute__(field)
        if not val and field != 'include':
            continue
        tp_record += field + ':'
        if field in multiline_fields:
            tp_record += '\n'
            for line in val.split('\n'):
                if line:
                    tp_record += ' ' + line + '\n'
        else:
            tp_record += ' ' + val + '\n'

    for symbol in tpu.fields.get_all_symbols():
        field = symbol.name
        if field not in write_order and '_' + field not in write_order:
            pass
            # print('extra field: {}'.format(field))
    return tp_record

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

    def get_unit_info(self, line, qualifier_unit):
        kind = 'unknown'
        extras = ''
        full_id = line
        ret_plugin = None
        if "::" not in full_id:
            qid = qualifier_unit.qualify_id(full_id)
            full_id = qid
        if '::after-suspend' in full_id:
            full_id = full_id.replace('::after-suspend-', '::')
            extras = '  <= {} REMOVED "after-suspend-" PREFIX'.format(full_id)
        if full_id in self.units.keys():
            plugin = self.units[full_id].plugin
            ret_plugin = plugin
            if plugin in ['shell', 'resource', 'attachment']:
                kind = 'automatic'
            else:
                kind = 'manual'
            if self.units[full_id].depends:
                for dep_id in self.units[full_id].depends.split():
                    dep_kind, _ = self.get_kind_for_unit(dep_id, self.units[full_id])
                    if dep_kind == 'manual':
                        extras += 'deps on manual'
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
            if not candidates:
                # ordinary matching: from include regex to template_ids
                for tid, tunit in self.template_units.items():
                    matches = re.match(full_id, tid)
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
                ret_plugin = tunit.get_record_value('plugin')
                if tunit.get_record_value('plugin') in ['shell', 'resource', 'attachment']:
                    kind = 'automatic'
                else:
                    kind = 'manual'
                if tunit.get_record_value('depends'):
                    for dep_id in tunit.get_record_value('depends').split():
                        dep_kind, _ = self.get_kind_for_unit(dep_id, tunit)
                        if dep_kind == 'manual':
                            extras += 'deps on man'
                            kind = 'manual'
        if not ret_plugin:
            ret_plugin = 'UNKNOWN'
        return ret_plugin, extras


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
            if not candidates:
                # ordinary matching: from include regex to template_ids
                for tid, tunit in self.template_units.items():
                    matches = re.match(full_id, tid)
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

    def split_tp(self, tpid):
        tp_unit = self.sa.get_test_plan(tpid)
        manuals = []
        autos = []
        unknowns = []
        for unit in self.get_run_sequence(tpid, True):
            if unit.kind == 'manual':
                manuals.append(unit)
            if unit.kind == 'automatic':
                autos.append(unit)
            if unit.kind == 'unknown':
                unknowns.append(unit)

        manual_tp = tpid[:-4] + 'manual'
        new_man_pxu = ""
        new_auto_pxu = ""
        if manual_tp not in self.all_tps:
            print("missing {}".format(manual_tp))
            new_man_tp = TestPlanUnit(tp_unit._raw_data)
            # remove the namespace prefix
            include_entries = []
            for unit in manuals:
                namespace = tp_unit.qualify_id('')
                if unit.id.startswith(namespace):
                    unit.id = unit.id.replace(namespace, '')
                include_entries.append(unit.id + unit.annotations)
            new_man_tp.id = unqualify_id(tp_unit, manual_tp)
            new_man_tp.include = "\n".join(include_entries)
            new_man_tp.name += ' (Manual)'
            new_man_tp.description += ' (Manual)'
            new_man_pxu = generate_tp_unit(new_man_tp)
        else:
            print("{} already there".format(manual_tp))
            man_seq = self.get_run_sequence(manual_tp)
            man_seq_ids = [unit.id for unit in man_seq]
            new_seq = [unit.id for unit in manuals]
            if man_seq_ids != new_seq:
                print("BUT HAS WRONG INCLUDE")
                print("FULL:\n{}\n\n VS \n\nMANUAL:\n{}".format(
                    "\n".join(new_seq), "\n".join(man_seq_ids)))
        auto_tp = tpid[:-4] + 'automated'
        if auto_tp not in self.all_tps:
            print("missing {}".format(auto_tp))
            new_auto_tp = TestPlanUnit(tp_unit._raw_data)
            # remove the namespace prefix
            include_entries = []
            for unit in autos:
                namespace = tp_unit.qualify_id('')
                if unit.id.startswith(namespace):
                    unit.id = unit.id.replace(namespace, '')
                include_entries.append(unit.id + unit.annotations)
            new_auto_tp.id = unqualify_id(tp_unit, auto_tp)
            new_auto_tp.include = "\n".join(include_entries)
            new_auto_tp.name += ' (Automated)'
            new_auto_tp.description += ' (Automated)'
            new_auto_pxu = generate_tp_unit(new_auto_tp)
        else:
            print("{} already there".format(auto_tp))
            auto_seq = self.get_run_sequence(auto_tp)
            auto_seq_ids = [unit.id for unit in auto_seq]
            new_seq = [unit.id for unit in autos]


            if auto_seq_ids != new_seq:
                print("BUT HAS DIFFERENT INCLUDE")
                print("FULL:\n{}\n\n VS \n\AUTOMATED:\n{}".format(
                    "\n".join(new_seq), "\n".join(auto_seq_ids)))
        if not new_man_pxu and not new_auto_pxu:
            return
        tp_unit.include = ""
        tp_unit.id = unqualify_id(tp_unit, tp_unit.id)
        tp_unit.nested_part = "\n".join([manual_tp, auto_tp])
        new_full_pxu = generate_tp_unit(tp_unit)
        with open(tp_unit.origin.source.filename, 'rt') as f:
            pxu = f.readlines()
        backup_path = tp_unit.origin.source.filename + '.bkp'
        if os.path.exists(backup_path):
            print("Backup file already present. Not overwriting: {}".format(
                backup_path))
        else:
            shutil.copyfile(tp_unit.origin.source.filename, backup_path)
            print("Backup made: {}".format(backup_path))

        new_pxu = pxu[:tp_unit.origin.line_start-1]
        new_pxu.append(new_full_pxu)
        new_pxu.append("\n")
        if new_man_pxu:
            new_pxu.append(new_man_pxu)
            new_pxu.append("\n")
        if new_auto_pxu:
            new_pxu.append(new_auto_pxu)
            new_pxu.append("\n")
        new_pxu += pxu[tp_unit.origin.line_end:]
        with open(tp_unit.origin.source.filename, 'wt') as f:
            f.write("".join(new_pxu))
        print("{} rewritten!".format(tp_unit.origin.source.filename))

    def annotated_tp(self, tp_id):
        tp_unit = self.sa.get_test_plan(tp_id)
        new_include = ''
        for line in tp_unit.include.split('\n'):
            if not line:
                new_include += line + '\n'
                continue
            if line.startswith('#'):
                new_include += line + '\n'
                continue
            if '#!-' in line:
                new_include += line + '\n'
                continue
            sections = line.split()
            annotations = line[len(sections[0]):]
            pattern = sections[0]
            pattern = pattern.split()[0]
            plugin, extras = self.get_unit_info(pattern, tp_unit)
            new_include += '{}    #!- {} - {}\n'.format(line, plugin, extras)
        tp_unit.include = new_include
        return generate_tp_unit(tp_unit)
