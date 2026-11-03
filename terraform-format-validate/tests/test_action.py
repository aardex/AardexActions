import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ACTION = Path(__file__).resolve().parents[1]

class ValidationContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        self.env.update(HOME=str(self.root), GITHUB_ACTION_PATH=str(ACTION),
                        GIT_CONFIG_NOSYSTEM='1', TF_IN_AUTOMATION='1',
                        TF_CLI_CONFIG_FILE=str(self.root / 'terraform.rc'))
        (self.root / 'terraform.rc').write_text('provider_installation { filesystem_mirror { path = "' + str(self.root) + '" } }\n')

    def run_script(self, name, *args, env=None, check=True):
        return subprocess.run(['bash', str(ACTION / name), *args], cwd=self.root,
                              env={**self.env, **(env or {})}, text=True,
                              capture_output=True, check=check)

    def test_no_credentials_backend_disabled_real_terraform(self):
        (self.root / 'main.tf').write_text('terraform { required_version = ">= 1.0" }\noutput "value" { value = "fixture" }\n')
        self.run_script('init.sh', env={'INIT_BACKEND': 'false'})
        subprocess.run(['terraform', 'validate', '-no-color'], cwd=self.root, env=self.env,
                       capture_output=True, text=True, check=True)
        self.assertFalse((self.root / '.gitconfig').exists())

    def test_init_credential_is_process_scoped(self):
        bindir = self.root / 'bin'
        bindir.mkdir()
        (bindir / 'terraform').write_text('#!/bin/bash\n[[ "$GIT_CONFIG_COUNT" == 1 ]] && [[ "$GIT_CONFIG_KEY_0" == *"synthetic-token"* ]] && [[ "$GIT_CONFIG_VALUE_0" == https://github.com/ ]] && [[ "$*" == *-backend=false* ]]\n')
        (bindir / 'terraform').chmod(0o755)
        self.run_script('init.sh', env={'PATH': str(bindir) + ':' + self.env['PATH'],
            'INIT_BACKEND': 'false', 'GH_MODULE_TOKEN': 'synthetic-token'})
        self.assertFalse((self.root / '.gitconfig').exists())

    def test_backend_default_and_invalid(self):
        bindir = self.root / 'bin'
        bindir.mkdir()
        (bindir / 'terraform').write_text('#!/bin/bash\n[[ "$*" == "init -upgrade -input=false" ]]\n')
        (bindir / 'terraform').chmod(0o755)
        env = {'PATH': str(bindir) + ':' + self.env['PATH']}
        self.run_script('init.sh', env=env)
        self.assertNotEqual(self.run_script('init.sh', env={**env, 'INIT_BACKEND':'invalid'}, check=False).returncode, 0)

    def test_push_disposable_bare_repository(self):
        bare = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(bare)], check=True, env=self.env)
        subprocess.run(['git', 'init', '-q', str(self.root / 'work')], check=True, env=self.env)
        work = self.root / 'work'
        def git(*args):
            subprocess.run(['git', *args], cwd=work, env=self.env, check=True, capture_output=True)
        git('config', 'user.email', 'test@example.invalid')
        git('config', 'user.name', 'Fixture')
        (work / 'file').write_text('fixture')
        git('add', 'file')
        git('commit', '-qm', 'fixture')
        git('remote', 'add', 'origin', str(bare))
        subprocess.run(['bash', str(ACTION / 'push.sh'), 'protected-branch'], cwd=work,
                       env={**self.env, 'GH_MODULE_TOKEN': 'synthetic-token'}, check=True, capture_output=True)
        git_result = subprocess.run(['git', '--git-dir', str(bare), 'rev-parse', 'refs/heads/protected-branch'],
                                    env=self.env, check=True, capture_output=True)
        self.assertTrue(git_result.stdout.strip())
        self.assertFalse((self.root / '.gitconfig').exists())

if __name__ == '__main__':
    unittest.main()
