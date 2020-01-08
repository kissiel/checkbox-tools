import collections
import concurrent
import datetime
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time

from concurrent.futures import ThreadPoolExecutor

class TaskPool:
    def __init__(self, workers = multiprocessing.cpu_count):
        self._queue = collections.deque()
        self._pool = ThreadPoolExecutor(max_workers=workers)
        self._task_map = dict()
    def add_task(self, task):
        self._queue.append(task)
        self._task_map[task.commit] = self._pool.submit(task.run)
    def run_and_wait(self):
        self._pool.shutdown()
        for commit, task in self._task_map.items():
            if task.exception():
                print("Task failed for commit {}. {}".format(commit, task.exception()))

class BenchmarkingTask:
    def __init__(self, path, commit):
        self._path = path
        self._commit = commit
    @property
    def commit(self):
        return self._commit
    def run(self):
        with tempfile.TemporaryDirectory(prefix='benchmarking-') as tmp:
            subprocess.run(['git', 'clone', '-l', self._path, tmp], check=True)
            subprocess.run(['git', 'reset', '--hard', self._commit], check=True, cwd=tmp)
            base_dir = os.path.split(os.path.abspath(__file__))[0]
            shutil.copytree(
                os.path.join(base_dir, '2019.com.canonical.certification:metabench'),
                os.path.join(tmp, '2019.com.canonical.certification:metabench')
            )
            shutil.copy(os.path.join(base_dir, 'benchmark.py'), os.path.join(tmp, 'benchmark.py'))

            try:
                os.chdir(tmp)
                for scenario in ['small', 'templatey', 'bootstrap-only']:
                    out = subprocess.check_output(['python3', 'benchmark.py', scenario])
                    elapsed = float(out.splitlines()[-1])
                    print('{} - {} : {}'.format(self._commit, scenario, elapsed))
            finally:
                os.chdir(base_dir)
            return

            commit_timestamp = subprocess.check_output('git show -s --format=%ct', shell=True).decode(sys.stdout.encoding)
            commit_dt = datetime.datetime.fromtimestamp(int(commit_timestamp))
            print(commit_dt)
            measurement = {
                'timestamp': commit_dt.timestamp(),
                'cpu': get_cpu_name(),
            }
            subprocess.run(". venv/bin/activate; pip3 install psutil", shell=True)
            subprocess.run(". venv/bin/activate; ../2019.com.canonical.certification:metabench/manage.py develop -d $PROVIDERPATH", shell=True)

            score_path = os.path.join(base_dir, 'measurements', commit)
            if not os.path.exists(score_path):
                print('{} info not found, benchmarking'.format(commit))
                scores = dict()
                for scenario in ['small', 'templatey', 'bootstrap-only']:
                    scores[scenario] = bench(scenario)
                    #scores[scenario] = 2.0
                measurement['scores'] = scores
                with open(score_path, 'wt') as f:
                    json.dump(measurement, f, indent='  ')
            else:
                with open(score_path, 'rt') as f:
                    measurement = json.load(f)
            reqobj = {'database': 'certsandbox', 'measurements': [{
                    'measurement': 'checkbox-perf',
                    'time': int(measurement['timestamp'] * 10 ** 9), # sec to nsec
                    'tags': {'cpu_name':measurement['cpu']},
                    'fields': measurement['scores'],
                }]}
            r = requests.post('http://bork.monospaced.pl:8000/influx', json=reqobj)
            print(tmp)

class GitRepo:
    # TODO: turn this into a context manager for easier cleanup
    def __init__(self, url):
        tmpdir = tempfile.mkdtemp(prefix='benchmarking-')
        subprocess.run(['git', 'clone', url, tmpdir])
        self._repo_path = tmpdir
    def get_merge_commits(self):
        history = subprocess.check_output(
            ['git', '-C', self._repo_path, 'log', '--pretty=%H', '--merges',])
        commits = history.decode(sys.stdout.encoding).splitlines()
        return commits
    def get_local_path(self):
        return self._roepo_path


def main():
    master_path = sys.argv[1]
    repo = GitRepo(master_path)
    commits = repo.get_merge_commits()
    pool = TaskPool(1)
    for commit in commits[:10]:
        pool.add_task(BenchmarkingTask(master_path, commit))
    pool.run_and_wait()



if __name__ == '__main__':
    main()
