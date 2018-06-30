#!/usr/bin/env python3

import contextlib
import os
import subprocess
import sys


wanted = [
    'plainbox-provider-checkbox',
    'plainbox-provider-resource',
    'plainbox-provider-snappy',
    'plainbox-provider-ipdt',
    'plainbox-provider-tpm2',
    'plainbox-provider-sru',
    'plainbox-provider-docker',
]


@contextlib.contextmanager
def changed_dir(new_dir):
    cur_dir = os.getcwd()
    os.chdir(new_dir)
    yield
    os.chdir(cur_dir)


def clone(p):
    print('Cloning {}'.format(p))
    if os.path.exists(p):
        print('{} already exists, skipping'.format(p))
        return True
    user = os.getlogin()
    url = 'git+ssh://{}@git.launchpad.net/{}'.format(user, p)
    if subprocess.run(['git', 'clone', '-q', url]).returncode != 0:
        raise SystemExit('Problem with cloning {}!'.format(p))


def pull(p):
    print('Pulling {}'.format(p))
    if not os.path.exists(p):
        raise SystemExit('{} does not exist!'.format(p))
    with changed_dir(p):
        cp = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stdout=subprocess.PIPE)
        if cp.returncode != 0:
            raise SystemExit(
                'Problem with getting current branch of {}!'.format(p))
        if cp.stdout.strip() != 'master':
            print('{} is not on master. Skipping.'.format(p))
            return
        cp = subprocess.run(['git', 'status', '--short'],
                            stdout=subprocess.PIPE)
        if len(cp.stdout) > 0:
            print('Status not clean on {}. Skipping.'.format(p))
            return
        if subprocess.run(['git', 'pull']).returncode != 0:
            raise SystemExit('Problem with pulling {}!'.format(p))


def develop(p):
    print('Running develop on {}'.format(p))
    prov_path = os.environ.get('PROVIDERPATH')
    if not prov_path:
        raise SystemExit('$PROVIDERPATH is not defined!'.format(p))
    if not os.path.exists(p):
        raise SystemExit('{} does not exist!'.format(p))
    with changed_dir(p):
        if os.path.exists('./manage.py'):
            manage_py_path = './manage.py'
        elif os.path.exists(os.path.join(p, './manage.py')):
            manage_py_path = os.path.join(p, './manage.py')
        else:
            print('manage.py not found for {}'.format(p))
        cp = subprocess.run([manage_py_path, 'develop', '-d', prov_path])
        if cp.returncode != 0:
            raise SystemExit('Problem with develop for {}!'.format(p))


def all(p):
    skipped = clone(p)
    if skipped:
        pull(p)
    develop(p)


commands = {
    'clone': clone,
    'pull': pull,
    'develop': develop,
    'all': all,
}


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
    else:
        cmd = 'all'
    if cmd not in commands.keys():
        raise SystemExit(
            "Supported commands are: ", ", ".join(commands.keys()))

    for provider in wanted:
        commands[cmd](provider)


if __name__ == '__main__':
    main()
