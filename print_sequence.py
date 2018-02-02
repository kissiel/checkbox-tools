#!/usr/bin/env python3

import re
import sys
from collections import namedtuple
from plainbox.abc import IJobQualifier
from plainbox.impl.session.assistant import SessionAssistant
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.template import TemplateUnit

sa = SessionAssistant('print_sequence')

units = dict()
template_units = dict()

def template_to_re(uid):
    #if 'com.canonical.certification::input/clicking' in uid:
    #    import pdb; pdb.set_trace()
    uid = uid.replace('{__index__}', r'\d+')
    greedy = re.sub(r'\{.+\}', '.+', uid)
    nongreedy = re.sub(r'\{.+?\}', '.+?', uid)
    return nongreedy, greedy


def generate_unit_map():
    for unit in sa._context._unit_list:
        u_type = type(unit)
        if u_type == TemplateUnit:
            unit.re_matcher, unit.re_greedy = template_to_re(unit.id)
            template_units[unit.id] = unit
        if not (issubclass(u_type, JobDefinition)):
            # print('skipping {}'.format(type(unit)))
            continue
        units[unit.id] = unit

def get_kind_for_unit(line, qualifier_unit):
    kind = 'unknown'
    extras = ''
    full_id = line
    if "::" not in full_id:
        qid = qualifier_unit.qualify_id(full_id)
        full_id = qid
    if '::after-suspend' in full_id:
        full_id = full_id.replace('::after-suspend-', '::')
        extras = '  <= {} REMOVED "after-suspend-" PREFIX'.format(full_id)
            
    if full_id in units.keys():
        plugin = units[full_id].plugin
        if plugin in ['shell', 'resource', 'attachment']:
            kind = 'automatic'
        else:
            kind = 'manual'
        if units[full_id].depends:
            for dep_id in units[full_id].depends.split():
                dep_kind, _ = get_kind_for_unit(dep_id, units[full_id]) 
                if dep_kind == 'manual':
                    if kind == 'automatic':
                        extras = 'manual b/c of dep on {}'.format(dep_id) + extras
                    kind = 'manual'



    if kind == 'unknown':
        candidates = []
        for tid, tunit in template_units.items():
            matches = re.match(tunit.re_matcher, full_id)
            if matches:
                candidates.append(tunit)
        if not candidates:
            for tid, tunit in template_units.items():
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
            tunit = template_units[tid]

        if tunit:
            if tunit.get_record_value('plugin') in ['shell', 'resource', 'attachment']:
                kind = 'automatic'
            else:
                kind = 'manual'
            if tunit.get_record_value('depends'):
                for dep_id in tunit.get_record_value('depends').split():
                    dep_kind, _ = get_kind_for_unit(dep_id, tunit)
                    if dep_kind == 'manual':
                        if kind == 'automatic':
                            extras = 'manual b/c of dep on {}'.format(dep_id) + extras
                        kind = 'manual'
            extras = '   <= {}'.format(tunit.id)
    return kind, extras

UnitProxy = namedtuple('UnitProxy', ['id', 'kind', 'extras', 'annotations'])


def get_run_sequence(tp_unit, include_nested = True):
    result = []
    if include_nested:
        for tp in tp_unit.get_nested_part():
            # print("NESTED {}".format(tp))
            result += get_run_sequence(sa.get_test_plan(tp.id))
    for line in tp_unit.include.split('\n'):
        if not line:
            continue
            
        if line.startswith('#'):
            continue
        sections = line.split()
        annotations = line[len(sections[0]):]
        line = sections[0]
        line = line.split()[0]
        kind, extras = get_kind_for_unit(line, tp_unit)

        result.append(UnitProxy(line, kind, extras, annotations))

    return result

    

def get_jobs_from_tp(tp_unit):
    selected = []
    quals = tp_unit.get_qualifier()
    for uid in units.keys():
        if quals.get_vote(units[uid]) == IJobQualifier.VOTE_INCLUDE:
            selected.append(uid)
    # also recursively visit nested test plans
    return selected

def init():
    generate_unit_map()



def main():

    tp = None
    if len(sys.argv) != 2:
        # raise SystemExit("Missing argument: test plan!")
        tp = 'com.canonical.ce::stella-full-16-04'
    else:
        tp = sys.argv[1]

    sa.select_providers('*')
    sa.start_new_session('print_sequence')
    all_tps = sa.get_test_plans()

    if tp not in all_tps:
        raise SystemExit('"{}" test plan not found!'.format(tp))


    init()
    tp_unit = sa.get_test_plan(tp)

    def list_tp_sets():
        fulls = [tp for tp in all_tps if tp.endswith('full')]
        for tp in fulls:
            basename = tp[:-4]
            others = [tp for tp in all_tps if tp.startswith(basename)]
            print(tp)
            for t in others:
                if t == tp: continue
                print(t)
            print('\n\n')
        print(fulls)


    new_units = dict()
    global units
    for uid in units.keys():
        if '{__index__}' in uid:
            for i in range(10):
                data = units[uid]._data.copy()
                data['id'] = uid.replace('{__index__}', str(i))
                new_units[data['id']] = TemplateUnit(data)
        else:
            new_units[uid] = units[uid]
    units = new_units




    #quals = tp_unit.get_qualifier()
    #for i in get_jobs_from_tp(tp_unit):
    #    print(i)
    #print(get_jobs_from_tp(tp_unit))
    #print(len(get_jobs_from_tp(tp_unit)))

    #import pdb; pdb.set_trace()
    #print(get_kind_for_unit('audio/playback_auto', tp_unit))

    for uid, kind, extras, annotations in get_run_sequence(tp_unit):
        print('{0:10}{1}{2: >130}'.format(kind, uid, extras).strip())


if __name__ == '__main__':
    main()
