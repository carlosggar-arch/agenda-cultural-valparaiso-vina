"""Historical browser datasets and their clock form one isolated fixture."""
import importlib.util
import ast
import json
import os
import tempfile
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('historical_scenarios', ROOT / 'app/scripts/run_browser_scenarios.py')
scenarios = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenarios)

@pytest.mark.parametrize('failed', [False, True])
def test_fixture_passes_its_clock_and_restores_current_bytes(tmp_path, monkeypatch, failed):
    dataset = tmp_path / 'agenda_web.json'
    original = b'{"current":"unchanged"}\n'
    dataset.write_bytes(original)
    historical = b'{"events":[],"publication_date":"2026-08-22"}\n'
    monkeypatch.setattr(scenarios, 'ROOT', tmp_path)
    monkeypatch.setattr(subprocess, 'check_output', lambda command, **kw: historical)
    calls = []
    def run(command, *, cwd, check, env):
        assert dataset.read_bytes() == historical
        assert json.loads(env['AGENDA_BROWSER_FIXTURE_CLOCKS']) == scenarios.HISTORICAL_DATASET_CLOCKS
        assert cwd == tmp_path and check is True
        calls.append(command)
        if failed: raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(subprocess, 'run', run)
    owner = 'app/scripts/test_runtime_user_flow_browser.py'
    if failed:
        with pytest.raises(subprocess.CalledProcessError): scenarios.run_browser_contract(['browser'], owner)
    else:
        scenarios.run_browser_contract(['browser'], owner)
    assert calls == [['browser']]
    assert dataset.read_bytes() == original

def test_current_production_contract_does_not_receive_historical_clock(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, 'run', lambda command, **kw: calls.append(kw))
    scenarios.run_browser_contract(['browser'], 'app/scripts/production_browser_selenium_smoke.py')
    assert calls == [{'cwd': scenarios.ROOT, 'check': True}]


@pytest.mark.parametrize('city', ['valparaiso', 'gijon'])
def test_city_fixture_clock_is_installed_before_navigation_only_for_fixture_city(monkeypatch, city):
    source = ast.parse((ROOT / 'app/scripts/test_runtime_browser.py').read_text())
    functions = [node for node in source.body if isinstance(node, ast.FunctionDef)
                 and node.name in {'freeze_browser_clock', 'run_city'}]
    calls = []
    class Driver:
        def execute_cdp_cmd(self, command, values): calls.append(('clock', command, values['source']))
        def get(self, url):
            calls.append(('navigation', url))
            raise ValueError('fixture stops before browser networking')
        def quit(self): pass
    namespace = {'os': os, 'json': json, 'tempfile': tempfile, 'TEST_PAGE': Path('__runtime_test.html'),
        'new_driver': lambda profile: Driver(), 'WebDriverWait': lambda *a, **kw: None}
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'runtime-fixture', 'exec'), namespace)
    monkeypatch.setenv('AGENDA_BROWSER_FIXTURE_CLOCKS', json.dumps(scenarios.HISTORICAL_DATASET_CLOCKS))
    with pytest.raises(AssertionError, match='fixture stops before browser networking'):
        namespace['run_city'](city, 'https://fixture.test')
    if city == 'valparaiso':
        assert [row[0] for row in calls] == ['clock', 'navigation', 'clock', 'navigation']
        assert calls[0][1] == 'Page.addScriptToEvaluateOnNewDocument'
        result = subprocess.check_output(['node', '-e', calls[0][2] +
            ';process.stdout.write(JSON.stringify([Date.now(), new Date().toISOString(),'
            'new Date("2001-01-01T00:00:00Z").toISOString()]))'], text=True)
        actual = json.loads(result)
        assert actual[1:] == ['2026-08-22T16:15:00.000Z', '2001-01-01T00:00:00.000Z']
    else:
        assert [row[0] for row in calls] == ['navigation', 'navigation']
