"""
Offline tests for node-level error handling (no DB, no network):

  - ErrorPolicy / RetryPolicy parsing and defaults
  - error classification (status codes, httpx exceptions, messages, billing)
  - ExecutionEngine._run_node_with_error_policy: retry, stop, continue, error_branch
  - error-branch routing and adjacency / fork-join exclusion of error edges
  - loop downstream failures bypass the loop's own policy
  - flow validator checks for errorHandling

Runs under pytest (``pytest tests/test_node_error_handling.py``) or standalone
(``python tests/test_node_error_handling.py``) from backend/.
"""
import asyncio
import contextlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from services import execution_engine as engine_module  # noqa: E402
from services.execution_engine import ExecutionEngine  # noqa: E402
from services.flow_validator import FlowValidator  # noqa: E402
from services.node_error_handling import (  # noqa: E402
    ErrorPolicy, NodeExecutionError, ServiceExecutionError, RetryPolicy,
    ON_ERROR_STOP, ON_ERROR_CONTINUE, ON_ERROR_BRANCH,
    classify_exception, unsuccessful_result_error, build_error_object,
    build_handled_output, mark_skip_policy, should_skip_policy,
)
from exceptions.billing_exceptions import BillingException  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


@contextlib.contextmanager
def _fake_db(*_args, **_kwargs):
    yield None


def make_engine():
    """Engine with DB, logging and WebSocket side effects stubbed out."""
    engine_module.get_tenant_db = _fake_db
    engine = ExecutionEngine('test_schema', 'tenant', 'user')
    engine.logs = []
    engine.notifications = []

    def _log(db, execution_id, step_id, level, message, data=None, context=None):
        engine.logs.append((step_id, level, message, data))

    async def _notify(execution_id, data):
        engine.notifications.append(data)

    async def _debug(execution_id, data):
        pass

    engine._log_execution = _log
    engine._send_status_notification = _notify
    engine._send_debug_event = _debug
    return engine


class FlakyHandler:
    """Fails ``failures`` times with ``exc`` then returns ``result``."""

    def __init__(self, failures, exc, result=None):
        self.failures = failures
        self.exc = exc
        self.result = result if result is not None else {'ok': True}
        self.calls = 0

    async def execute(self, node_data, context, engine_ctx):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exc
        return self.result


def policy(on_error='stop', retry=None, **extra):
    config = {'onError': on_error, **extra}
    if retry is not None:
        config['retry'] = retry
    return ErrorPolicy.from_node('action', {'errorHandling': config})


FAST_RETRY = {'enabled': True, 'maxAttempts': 3, 'initialDelayMs': 0, 'jitter': False}


def run_policy(engine, handler, pol, node_type='action'):
    context = {'execution_id': 'exec-1', 'data': {}, 'node_outputs': {}}
    return run(engine._run_node_with_error_policy(
        'node_1', node_type, {'label': 'Node 1'}, handler, None, context, pol))


# ---------------------------------------------------------------------------
# policy parsing
# ---------------------------------------------------------------------------

def test_default_policy_without_config_is_stop_without_retry():
    pol = ErrorPolicy.from_node('action', {'label': 'x'})
    assert pol.on_error == ON_ERROR_STOP
    assert not pol.retry.enabled
    assert not pol.handles_errors


def test_policy_parsing_clamps_and_filters():
    pol = ErrorPolicy.from_node('action', {'errorHandling': {
        'onError': 'error_branch',
        'retry': {'enabled': True, 'maxAttempts': 99, 'initialDelayMs': -5,
                  'backoff': 'weird', 'retryOn': ['server', 'bogus']},
    }})
    assert pol.on_error == ON_ERROR_BRANCH
    assert pol.retry.max_attempts == 10
    assert pol.retry.initial_delay_ms == 0
    assert pol.retry.backoff == 'exponential'
    assert pol.retry.retry_on == ['server']


def test_unknown_on_error_falls_back_to_stop():
    assert ErrorPolicy.from_node('action', {'errorHandling': {'onError': 'explode'}}).on_error == ON_ERROR_STOP


def test_retry_disabled_for_non_retryable_and_trigger_ignored():
    loop = ErrorPolicy.from_node('loop', {'errorHandling': {'onError': 'continue', 'retry': FAST_RETRY}})
    assert loop.on_error == ON_ERROR_CONTINUE and not loop.retry.enabled
    trigger = ErrorPolicy.from_node('trigger', {'errorHandling': {'onError': 'continue'}})
    assert trigger.on_error == ON_ERROR_STOP


def test_backoff_delays():
    exp = RetryPolicy(enabled=True, initial_delay_ms=1000, backoff='exponential', max_delay_ms=3000, jitter=False)
    assert [exp.delay_seconds(n) for n in (1, 2, 3)] == [1.0, 2.0, 3.0]
    fixed = RetryPolicy(enabled=True, initial_delay_ms=500, backoff='fixed', jitter=False)
    assert fixed.delay_seconds(4) == 0.5


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

def test_classify_status_codes():
    cases = {401: 'auth', 403: 'auth', 404: 'not_found', 408: 'timeout', 422: 'validation',
             429: 'rate_limit', 500: 'server', 503: 'server', 418: 'client'}
    for status, expected in cases.items():
        assert classify_exception(ServiceExecutionError('x', status_code=status)) == (expected, status)


def test_classify_exception_kinds():
    request = httpx.Request('GET', 'https://example.com')
    assert classify_exception(httpx.ReadTimeout('slow', request=request))[0] == 'timeout'
    assert classify_exception(httpx.ConnectError('down', request=request))[0] == 'connection'
    response = httpx.Response(502, request=request)
    status_error = httpx.HTTPStatusError('bad gateway', request=request, response=response)
    assert classify_exception(status_error) == ('server', 502)
    assert classify_exception(Exception('API request failed with status 429'))[0] == 'rate_limit'
    assert classify_exception(Exception('api_call authentication failed'))[0] == 'auth'
    assert classify_exception(ValueError('bad input'))[0] == 'validation'
    assert classify_exception(RuntimeError('???'))[0] == 'unknown'
    assert classify_exception(BillingException('no funds'))[0] == 'billing'
    assert classify_exception(NodeExecutionError('x', error_type='rate_limit'))[0] == 'rate_limit'


def test_unsuccessful_result_detection():
    assert unsuccessful_result_error({'success': True, 'data': 1}) is None
    assert unsuccessful_result_error('plain') is None
    err = unsuccessful_result_error({'success': False, 'status': 503, 'data': {'e': 1}})
    assert err.status_code == 503 and err.error_type == 'server'


def test_error_object_and_handled_output():
    exc = ServiceExecutionError('boom', status_code=500, response={'detail': 'x'})
    error = build_error_object(exc, node_id='n', node_type='action', node_label='N',
                               attempts=2, handled_by=ON_ERROR_BRANCH)
    assert error['type'] == 'server' and error['attempts'] == 2 and error['retryable']
    assert error['response'] == {'detail': 'x'}
    out = build_handled_output(policy('continue', continueOutput={'items': []}), error)
    assert out['items'] == [] and out['success'] is False and out['error'] is error


# ---------------------------------------------------------------------------
# policy runner
# ---------------------------------------------------------------------------

def test_success_passes_through():
    engine = make_engine()
    result, error = run_policy(engine, FlakyHandler(0, None, {'v': 1}), policy())
    assert result == {'v': 1} and error is None


def test_retry_then_succeed():
    engine = make_engine()
    handler = FlakyHandler(2, ServiceExecutionError('down', status_code=503))
    result, error = run_policy(engine, handler, policy('stop', FAST_RETRY))
    assert handler.calls == 3 and error is None and result == {'ok': True}
    assert sum(1 for n in engine.notifications if n['type'] == 'node_retry') == 2


def test_retry_skips_non_matching_error_types():
    engine = make_engine()
    handler = FlakyHandler(5, ServiceExecutionError('bad', status_code=400))
    try:
        run_policy(engine, handler, policy('stop', FAST_RETRY))
        assert False, 'expected raise'
    except ServiceExecutionError as e:
        assert handler.calls == 1
        assert e._ioflow_attempts == 1


def test_retry_any_retries_everything():
    engine = make_engine()
    handler = FlakyHandler(5, ValueError('bad'))
    result, error = run_policy(engine, handler, policy('continue', {**FAST_RETRY, 'retryOn': ['any']}))
    assert handler.calls == 3
    assert error['attempts'] == 3 and error['type'] == 'validation'


def test_stop_reraises():
    engine = make_engine()
    try:
        run_policy(engine, FlakyHandler(1, RuntimeError('boom')), policy('stop'))
        assert False, 'expected raise'
    except RuntimeError as e:
        assert str(e) == 'boom'


def test_continue_and_branch_return_handled_output():
    for mode in (ON_ERROR_CONTINUE, ON_ERROR_BRANCH):
        engine = make_engine()
        result, error = run_policy(engine, FlakyHandler(1, RuntimeError('boom')), policy(mode))
        assert error['message'] == 'boom' and error['handled_by'] == mode
        assert result['success'] is False and result['error'] is error


def test_billing_errors_are_never_handled():
    engine = make_engine()
    handler = FlakyHandler(5, BillingException('no funds'))
    try:
        run_policy(engine, handler, policy('continue', {**FAST_RETRY, 'retryOn': ['any']}))
        assert False, 'expected raise'
    except BillingException:
        assert handler.calls == 1


def test_fail_on_unsuccessful_response():
    engine = make_engine()
    soft = {'success': False, 'status': 500, 'data': {}}
    result, error = run_policy(engine, FlakyHandler(0, None, soft), policy('error_branch'))
    assert error is None  # opt-in only
    result, error = run_policy(engine, FlakyHandler(0, None, soft),
                               policy('error_branch', failOnUnsuccessfulResponse=True))
    assert error['type'] == 'server' and error['status_code'] == 500


def test_downstream_failures_bypass_policy():
    engine = make_engine()
    exc = RuntimeError('downstream')
    mark_skip_policy(exc, 'node_1')
    assert should_skip_policy(exc, 'node_1') and not should_skip_policy(exc, 'other')
    try:
        run_policy(engine, FlakyHandler(1, exc), policy('continue'))
        assert False, 'expected raise'
    except RuntimeError:
        pass


def test_loop_exit_signal_is_not_handled():
    engine = make_engine()
    try:
        run_policy(engine, FlakyHandler(1, Exception('Loop exit')), policy('continue'))
        assert False, 'expected raise'
    except Exception as e:
        assert 'Loop exit' in str(e)


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------

EDGES = [
    {'source': 'a', 'target': 'b', 'sourceHandle': 'bottom'},
    {'source': 'a', 'target': 'h', 'sourceHandle': 'error'},
    {'source': 'b', 'target': 'h', 'sourceHandle': 'bottom'},
]


def test_adjacency_excludes_error_edges():
    engine = make_engine()
    assert engine._build_adjacency_list(EDGES) == {'a': ['b'], 'b': ['h']}
    # h is joined only by b; the error edge from a must not make it wait for a
    assert engine._build_reverse_adjacency_list(EDGES) == {'b': ['a'], 'h': ['b']}


def test_follow_error_branch_executes_error_targets_only():
    engine = make_engine()
    executed = []

    async def fake_execute(node, all_nodes, edges, adjacency, context):
        executed.append(node['id'])

    engine._execute_node = fake_execute
    nodes = [{'id': n, 'type': 'action', 'data': {}} for n in ('a', 'b', 'h')]
    context = {'execution_id': 'e', '_completed_nodes': set()}
    run(engine._follow_error_branch('a', nodes, EDGES, {}, context))
    assert executed == ['h'] and 'a' in context['_completed_nodes']

    executed.clear()
    run(engine._follow_error_branch('b', nodes, EDGES, {}, context))
    assert executed == []
    assert any('no node is connected' in log[2] for log in engine.logs)


JOIN_EDGES = [
    {'source': 'fail', 'target': 'ok', 'sourceHandle': 'bottom'},
    {'source': 'ok', 'target': 'join', 'sourceHandle': 'bottom'},
    {'source': 'fail', 'target': 'handle', 'sourceHandle': 'error'},
    {'source': 'handle', 'target': 'join', 'sourceHandle': 'bottom'},
]


def _join_setup():
    engine = make_engine()
    executed = []

    async def fake_execute(node, all_nodes, edges, adjacency, context):
        executed.append(node['id'])

    engine._execute_node = fake_execute
    nodes = [{'id': n, 'type': 'action', 'data': {}} for n in ('fail', 'ok', 'handle', 'join')]
    context = {
        'execution_id': 'e', '_completed_nodes': set(), '_all_nodes': nodes,
        '_reverse_adjacency': engine._build_reverse_adjacency_list(JOIN_EDGES),
    }
    return engine, executed, nodes, context, engine._build_adjacency_list(JOIN_EDGES)


def test_dead_path_lets_error_branch_rejoin():
    engine, executed, nodes, context, adjacency = _join_setup()
    # 'fail' takes its error branch: fail -> ok -> join is dead
    run(engine._propagate_dead_path('fail', 'ok', nodes, JOIN_EDGES, adjacency, context))
    assert ('fail', 'ok') in context['_dead_edges'] and ('ok', 'join') in context['_dead_edges']
    assert executed == []  # join still waits for the error branch
    # the error branch reaches the join: it may run now
    assert run(engine._can_execute_node('handle', 'join', context)) is True


def test_join_waiting_on_skipped_input_runs_when_it_dies():
    engine, executed, nodes, context, adjacency = _join_setup()
    context['_completed_nodes'].add('handle')  # error branch arrived first
    run(engine._propagate_dead_path('fail', 'ok', nodes, JOIN_EDGES, adjacency, context))
    assert executed == ['join']


def test_join_without_dead_edges_still_waits():
    engine, executed, nodes, context, adjacency = _join_setup()
    assert run(engine._can_execute_node('handle', 'join', context)) is False


def test_execute_downstream_marks_exception():
    engine = make_engine()

    async def failing(node, all_nodes, edges, adjacency, context):
        raise RuntimeError('after loop')

    engine._execute_node = failing
    try:
        run(engine._execute_downstream_of('loop_1', {'id': 'x'}, [], [], {}, {}))
        assert False, 'expected raise'
    except RuntimeError as e:
        assert should_skip_policy(e, 'loop_1')


def test_error_namespace_variable():
    engine = make_engine()
    context = {'variables': {'error': 'plain var'}, 'node_outputs': {}}
    assert engine._get_field_value('error', context) == 'plain var'
    context['last_error'] = {'message': 'boom', 'type': 'server'}
    assert engine._get_field_value('error.message', context) == 'boom'


# ---------------------------------------------------------------------------
# validator
# ---------------------------------------------------------------------------

def _messages(nodes, edges):
    return [e.message for e in FlowValidator()._validate_error_handling(nodes, edges)]


def test_validator_error_handling_checks():
    node = lambda nid, eh=None: {'id': nid, 'type': 'action',
                                 'data': {'label': nid, **({'errorHandling': eh} if eh else {})}}
    # error_branch without an error edge
    msgs = _messages([node('a', {'onError': 'error_branch'})], [])
    assert any('nothing is connected' in m for m in msgs)
    # error edge without error_branch
    msgs = _messages([node('a', {'onError': 'continue'}), node('h')],
                     [{'source': 'a', 'target': 'h', 'sourceHandle': 'error'}])
    assert any('never runs' in m for m in msgs)
    # error edge with no config at all
    msgs = _messages([node('a'), node('h')], [{'source': 'a', 'target': 'h', 'sourceHandle': 'error'}])
    assert any('no error handling configured' in m for m in msgs)
    # unknown mode is an error
    errs = FlowValidator()._validate_error_handling([node('a', {'onError': 'nope'})], [])
    assert any(e.error_type == 'error' for e in errs)
    # valid config produces nothing
    assert _messages([node('a', {'onError': 'error_branch', 'retry': FAST_RETRY}), node('h')],
                     [{'source': 'a', 'target': 'h', 'sourceHandle': 'error'}]) == []


if __name__ == '__main__':
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith('test_') and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
