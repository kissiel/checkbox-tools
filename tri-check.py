#!/usr/bin/env python3
import os
import re
import shutil
import sys
from plainbox.abc import IJobQualifier
from plainbox.impl.session.assistant import SessionAssistant
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.template import TemplateUnit
from plainbox.impl.unit.testplan import TestPlanUnit

from print_sequence import init, get_run_sequence
import print_sequence

sa = print_sequence.sa 

def unqualify_id(tp_unit, uid):
    namespace = tp_unit.qualify_id('')
    if uid.startswith(namespace):
        return  uid.replace(namespace, '')
    else:
        return uid


def print_missing(all_tps):
    endings = ['full', 'manual', 'automated']
    for ending in endings:
        to_check = endings.copy()
        to_check.remove(ending)
        for tp in all_tps:
            missing = []
            if tp.endswith(ending):
                base = tp[:-len(ending)]
                for e in to_check:
                    if base+e not in all_tps:
                        missing.append(base+e)
            if missing:
                print("+++ {}".format(tp))
                for m in missing:
                    print("  + MISSING: {}".format(m))

def write_tp_unit(tpu):
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

def check_tp(tpid, all_tps):
    tp_unit = sa.get_test_plan(tpid)
    manuals = []
    autos = []
    unknowns = []
    for unit in get_run_sequence(tp_unit, True):
        if unit.kind == 'manual':
            manuals.append(unit)
        if unit.kind == 'automatic':
            autos.append(unit)
        if unit.kind == 'unknown':
            unknowns.append(unit)

    manual_tp = tpid[:-4] + 'manual' 
    new_man_pxu = ""
    new_auto_pxu = ""
    
    if manual_tp not in all_tps:
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
        new_man_pxu = write_tp_unit(new_man_tp)
    else:
        print("{} already there")
        man_seq = get_run_sequence(sa.get_test_plan(manual_tp))
        man_seq_ids = [uid for uid, kind, extras in man_seq]
        if man_seq_ids != manuals:
            print("BUT HAS WRONG INCLUDE")
            print("FULL:\n{}\n\n VS \n\nMANUAL:\n{}".format(
                "\n".join(manuals), "\n".join(man_seq_ids)))
    auto_tp = tpid[:-4] + 'automated' 
    if auto_tp not in all_tps:
        # print("missing {}".format(auto_tp))
        new_auto_tp = TestPlanUnit(tp_unit._raw_data)
        # remove the namespace prefix
        include_entries = []
        for unit in autos:
            unqualified_ids.append(unqualify_id(tp_unit, unit.id))
        new_auto_tp.id = unqualify_id(tp_unit, auto_tp)
        new_auto_tp.include = "\n".join(include_entries)
        new_auto_tp.name += ' (Automated)'
        new_auto_tp.description += ' (Automated)'
        new_auto_pxu = write_tp_unit(new_auto_tp)
    else:
        print("{} already there")
        auto_seq = get_run_sequence(sa.get_test_plan(auto_tp))
        auto_seq_ids = [unit.id for unit in auto_seq]
        if auto_seq_ids != autos:
            print("BUT HAS WRONG INCLUDE")
            print("FULL:\n{}\n\n VS \n\AUTOMATED:\n{}".format(
                "\n".join(autos), "\n".join(auto_seq_ids)))
    if not new_man_pxu and not new_auto_pxu:
        return
    tp_unit.include = ""
    tp_unit.id = unqualify_id(tp_unit, tp_unit.id)
    tp_unit.nested_part = "\n".join([manual_tp, auto_tp])
    new_full_pxu = write_tp_unit(tp_unit)
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
    new_pxu.append(new_man_pxu)
    new_pxu.append("\n")
    new_pxu.append(new_auto_pxu)
    new_pxu.append("\n")
    new_pxu += pxu[tp_unit.origin.line_end-1:]
    with open(tp_unit.origin.source.filename, 'wt') as f:
        f.write("".join(new_pxu))
    print("{} rewritten!".format(tp_unit.origin.source.filename))

    if False:
        print("MANUAL:")
        for i in manuals: print(i)
        print("AUTOMATIC:")
        for i in autos: print(i)
        print("UNKNOWNS:")
        for i in unknowns: print(i)



def main():
    sa.select_providers('*')
    sa.start_new_session('tri_check')
    all_tps = sa.get_test_plans()
    init()
    if len(sys.argv) > 1:
        all_tps = sys.argv[1:]

    for tp in all_tps:
        if tp.endswith('full'):
            # print('analyzing {}'.format(tp))
            tp_unit = sa.get_test_plan(tp)
            if not tp_unit.nested_part:
                check_tp(tp, all_tps)
                #print(tp)
            #write_tp_unit(tp_unit)
            #seq = get_run_sequence(tp_unit, False)
            #if seq:
            #    print("{} explicitly includes units".format(tp))
            #for uid, kind, extras in seq:
            #    print('{0:10}{1}{2: >130}'.format(kind, uid, extras).strip())

if __name__ == '__main__':
    main()
