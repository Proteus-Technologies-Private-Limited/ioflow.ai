"""
Offline tests for the e-commerce engine extensions (no network):

  E1  auth_config.access_token_header / access_token_prefix
  E2  {{auth.<field>}} in base_url / token_url / endpoint_template, and
      auth_config.token_request {method, params_in, extra_params}
  E3  request_config.body_jinja / query_jinja / query_list_format / encode_path_params
  E4  response_config.output_jinja / keep_raw / success_jinja / error_jinja
  E5  request_config.no_request
  +   shared Jinja filters, webhook body-signature verification, seed validation

Runs under pytest (``pytest tests/test_ecommerce_engine_extensions.py``) or
standalone (``python tests/test_ecommerce_engine_extensions.py``) from backend/.
"""
import asyncio
import base64
import contextlib
import hashlib
import hmac
import json
import os
import sys
from typing import Any, Callable, Dict, List
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from services.service_executors import ApiCallExecutor, ServiceExecutor  # noqa: E402
from services import oauth2_manager as oauth2_module  # noqa: E402
from services.jinja_templating import (  # noqa: E402
    FILTERS, TemplateRenderError, render_auth_placeholders, render_json,
)
from services.webhook_verification import get_signature_config, verify_body_signature  # noqa: E402
from utils.crypto_utils import encrypt_credentials, decrypt_credentials  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_RealAsyncClient = httpx.AsyncClient


@contextlib.contextmanager
def mock_http(handler: Callable[[httpx.Request], httpx.Response]):
    """Route every httpx.AsyncClient created inside the block through MockTransport."""
    captured: List[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        request.read()
        captured.append(request)
        return handler(request)

    def _factory(*args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(_handler)
        return _RealAsyncClient(*args, **kwargs)

    httpx.AsyncClient = _factory
    try:
        yield captured
    finally:
        httpx.AsyncClient = _RealAsyncClient


def run(coro):
    return asyncio.run(coro)


def json_response(payload: Any, status: int = 200, headers: Dict[str, str] = None) -> httpx.Response:
    return httpx.Response(status, json=payload, headers=headers or {})


def make_executor(service_config: Dict[str, Any], credentials: Dict[str, Any] = None,
                  auth_config: Dict[str, Any] = None) -> ApiCallExecutor:
    # No subscription_id => the executor never tries a token refresh against a DB.
    return ApiCallExecutor(service_config, credentials or {}, None, auth_config or {})


class _FakeQuery:
    def __init__(self, subscription):
        self._subscription = subscription

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._subscription


class _FakeSubscription:
    def __init__(self, credentials):
        self.subscription_id = 'sub-1'
        self.auth_credentials = encrypt_credentials(credentials)


class _FakeDb:
    def __init__(self, subscription):
        self.subscription = subscription
        self.commits = 0

    def query(self, *args, **kwargs):
        return _FakeQuery(self.subscription)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


# ---------------------------------------------------------------------------
# E1 - access token header placement
# ---------------------------------------------------------------------------

def test_e1_default_authorization_bearer_unchanged():
    ex = ServiceExecutor({}, {'access_token': 'tok', 'token_type': 'Bearer'}, None, {'token_url': 'x'})
    assert ex._build_auth_headers() == {'Authorization': 'Bearer tok'}


def test_e1_amazon_x_amz_access_token_bare():
    ex = ServiceExecutor({}, {'access_token': 'Atza|abc', 'token_type': 'bearer'}, None,
                         {'access_token_header': 'x-amz-access-token', 'access_token_prefix': ''})
    headers = ex._build_auth_headers()
    assert headers == {'x-amz-access-token': 'Atza|abc'}
    assert 'Authorization' not in headers


def test_e1_shopify_header_bare():
    ex = ServiceExecutor({}, {'access_token': 'shpat_1'}, None,
                         {'access_token_header': 'X-Shopify-Access-Token', 'access_token_prefix': ''})
    assert ex._build_auth_headers() == {'X-Shopify-Access-Token': 'shpat_1'}


def test_e1_header_with_default_prefix_from_token_type():
    ex = ServiceExecutor({}, {'access_token': 't', 'token_type': 'Token'}, None,
                         {'access_token_header': 'X-Auth'})
    assert ex._build_auth_headers() == {'X-Auth': 'Token t'}
    ex2 = ServiceExecutor({}, {'access_token': 't'}, None, {'access_token_header': 'X-Auth'})
    assert ex2._build_auth_headers() == {'X-Auth': 'Bearer t'}


# ---------------------------------------------------------------------------
# E2 - per-connection URLs + token request shape
# ---------------------------------------------------------------------------

def test_e2_base_url_rendered_from_credentials():
    cfg = {
        'service_name': 'list_orders',
        'base_url': 'https://{{auth.shop_domain}}/admin/api/2026-07',
        'endpoint_template': '/graphql.json',
        'request_config': {'method': 'POST', 'body_jinja': '{"query": "{ shop { name } }"}'},
    }
    ex = make_executor(cfg, {'access_token': 'shpat', 'shop_domain': 'acme.myshopify.com'},
                       {'access_token_header': 'X-Shopify-Access-Token', 'access_token_prefix': ''})
    with mock_http(lambda r: json_response({'data': {'shop': {'name': 'Acme'}}})) as calls:
        result = run(ex.execute({}, {}))
    assert result['success'] is True, result
    assert str(calls[0].url) == 'https://acme.myshopify.com/admin/api/2026-07/graphql.json'
    assert calls[0].headers['X-Shopify-Access-Token'] == 'shpat'
    assert 'authorization' not in calls[0].headers


def test_e2_base_url_missing_field_is_a_clear_error_and_no_call():
    cfg = {'service_name': 's', 'base_url': 'https://{{auth.shop_domain}}/admin', 'endpoint_template': '/x',
           'request_config': {'method': 'GET'}}
    ex = make_executor(cfg, {'access_token': 't'})
    with mock_http(lambda r: json_response({})) as calls:
        result = run(ex.execute({}, {}))
    assert result['error'] is True
    assert 'shop_domain' in result['message']
    assert calls == []


def test_e2_endpoint_template_auth_placeholder():
    cfg = {'service_name': 's', 'base_url': 'https://api.example.com',
           'endpoint_template': '/sellers/{{auth.seller_id}}/listings/{{sku}}',
           'request_config': {'method': 'GET', 'encode_path_params': True}}
    ex = make_executor(cfg, {'api_key': 'k', 'seller_id': 'S 1'})
    with mock_http(lambda r: json_response({'ok': True})) as calls:
        result = run(ex.execute({'sku': 'AB/12 X'}, {}))
    assert result['success'] is True
    assert calls[0].url.raw_path.decode() == '/sellers/S%201/listings/AB%2F12%20X'


def test_e2_path_params_not_encoded_by_default():
    cfg = {'service_name': 's', 'base_url': 'https://api.example.com', 'endpoint_template': '/items/{{id}}',
           'request_config': {'method': 'GET'}}
    ex = make_executor(cfg, {'api_key': 'k'})
    with mock_http(lambda r: json_response({})) as calls:
        run(ex.execute({'id': 'a/b'}, {}))
    assert calls[0].url.raw_path.decode() == '/items/a/b'


def test_e2_token_url_rendering_and_missing_field():
    assert render_auth_placeholders('{{auth.endpoint}}/oauth-service/oauth/token',
                                    {'endpoint': 'https://sandbox-api.flipkart.net'}, 'token_url') \
        == 'https://sandbox-api.flipkart.net/oauth-service/oauth/token'
    try:
        render_auth_placeholders('https://{{ auth.shop_domain }}/admin/oauth/access_token', {}, 'The OAuth2 token_url')
        raise AssertionError('expected TemplateRenderError')
    except TemplateRenderError as e:
        assert 'shop_domain' in str(e)


def test_e2_flipkart_get_token_with_basic_auth_and_query_params():
    auth_config = {
        'token_url': '{{auth.endpoint}}/oauth-service/oauth/token',
        'auth_method': 'basic',
        'token_request': {'method': 'GET', 'params_in': 'query', 'extra_params': {'scope': 'Seller_Api'}},
    }
    creds = {'client_id': 'cid', 'client_secret': 'csec', 'endpoint': 'https://api.flipkart.net'}
    mgr = oauth2_module.OAuth2TokenManager()
    with mock_http(lambda r: json_response({'access_token': 'fk', 'token_type': 'bearer', 'expires_in': 3600})) as calls:
        token = run(mgr._request_new_token(auth_config=auth_config, client_id='cid', client_secret='csec',
                                           credentials=creds))
    assert token['access_token'] == 'fk' and token['expires_at']
    req = calls[0]
    assert req.method == 'GET'
    parsed = urlparse(str(req.url))
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == 'https://api.flipkart.net/oauth-service/oauth/token'
    assert parse_qs(parsed.query) == {'grant_type': ['client_credentials'], 'scope': ['Seller_Api']}
    assert req.headers['Authorization'] == 'Basic ' + base64.b64encode(b'cid:csec').decode()
    assert req.content == b''


def test_e2_amazon_lwa_refresh_token_post_form_unchanged():
    auth_config = {'token_url': 'https://api.amazon.com/auth/o2/token', 'authorization_url': 'x'}
    mgr = oauth2_module.OAuth2TokenManager()
    with mock_http(lambda r: json_response({'access_token': 'Atza|x', 'token_type': 'bearer', 'expires_in': 3600})) as calls:
        token = run(mgr._request_new_token(auth_config=auth_config, client_id='amzn1.id', client_secret='sec',
                                           refresh_token='Atzr|refresh'))
    assert token['access_token'] == 'Atza|x'
    req = calls[0]
    assert req.method == 'POST' and str(req.url) == 'https://api.amazon.com/auth/o2/token'
    assert req.headers['Content-Type'] == 'application/x-www-form-urlencoded'
    assert parse_qs(req.content.decode()) == {
        'grant_type': ['refresh_token'], 'refresh_token': ['Atzr|refresh'],
        'client_id': ['amzn1.id'], 'client_secret': ['sec']}


def test_e2_shopify_client_credentials_without_refresh_token_and_merge_on_save():
    auth_config = {'token_url': 'https://{{auth.shop_domain}}/admin/oauth/access_token',
                   'grant_type': 'client_credentials'}
    # Stored set holds a field the in-flight credentials do not carry; it must survive.
    stored = {'client_id': 'cid', 'client_secret': 'csec', 'shop_domain': 'acme.myshopify.com',
              'seller_id': 'KEEP-ME', 'access_token': 'old', 'expires_at': 1}
    current = {'client_id': 'cid', 'client_secret': 'csec', 'shop_domain': 'acme.myshopify.com',
               'access_token': 'old', 'expires_at': 1}
    db = _FakeDb(_FakeSubscription(stored))
    mgr = oauth2_module.OAuth2TokenManager()
    with mock_http(lambda r: json_response({'access_token': 'shpat_new', 'scope': 'read_orders',
                                            'expires_in': 86399})) as calls:
        updated = run(mgr.get_valid_token('sub-1', auth_config, current, db))
    req = calls[0]
    assert str(req.url) == 'https://acme.myshopify.com/admin/oauth/access_token'
    assert parse_qs(req.content.decode())['grant_type'] == ['client_credentials']
    assert updated['access_token'] == 'shpat_new' and updated['expires_at'] > 1
    saved = decrypt_credentials(db.subscription.auth_credentials)
    assert saved['access_token'] == 'shpat_new'
    assert saved['seller_id'] == 'KEEP-ME' and saved['shop_domain'] == 'acme.myshopify.com'


def test_e2_client_credentials_failure_message_is_not_about_refresh_tokens():
    auth_config = {'token_url': 'https://x.example/token', 'grant_type': 'client_credentials'}
    mgr = oauth2_module.OAuth2TokenManager()
    with mock_http(lambda r: json_response({'error': 'invalid_client'}, status=401)):
        try:
            run(mgr.get_valid_token('sub-1', auth_config, {'client_id': 'a', 'client_secret': 'b'}, _FakeDb(None)))
            raise AssertionError('expected ValueError')
        except ValueError as e:
            assert 'client_credentials' in str(e)


# ---------------------------------------------------------------------------
# E3 - Jinja request templates
# ---------------------------------------------------------------------------

def test_e3_body_jinja_loop_and_dynamic_keys():
    body_jinja = (
        '{ {% for it in items %}{{ it.sku | tojson }}: {"product_id": {{ it.pid | tojson }}, '
        '"locations": [{"id": {{ auth.location_id | tojson }}, "inventory": {{ it.qty | to_int }}}]}'
        '{% if not loop.last %}, {% endif %}{% endfor %} }'
    )
    cfg = {'service_name': 'update_inventory', 'base_url': 'https://api.flipkart.net/sellers',
           'endpoint_template': '/listings/v3/update/inventory',
           'request_config': {'method': 'POST', 'body_jinja': body_jinja}}
    ex = make_executor(cfg, {'access_token': 't', 'location_id': 'LOC1'})
    params = {'items': [{'sku': 'SKU-1', 'pid': 'P1', 'qty': '5'}, {'sku': 'Dress/Red L', 'pid': 'P2', 'qty': 2.0}]}
    with mock_http(lambda r: json_response({'SKU-1': {'status': 'SUCCESS'}})) as calls:
        result = run(ex.execute(params, {}))
    assert result['success'] is True
    body = json.loads(calls[0].content)
    assert body == {
        'SKU-1': {'product_id': 'P1', 'locations': [{'id': 'LOC1', 'inventory': 5}]},
        'Dress/Red L': {'product_id': 'P2', 'locations': [{'id': 'LOC1', 'inventory': 2}]},
    }
    assert calls[0].headers['Content-Type'] == 'application/json'


def test_e3_body_jinja_context_has_params_and_now_iso():
    cfg = {'service_name': 's', 'base_url': 'https://h', 'endpoint_template': '/x',
           'request_config': {'method': 'POST',
                              'body_jinja': '{"n": {{ params.n | tojson }}, "same": {{ n | tojson }}, "at": {{ now_iso | tojson }}}'}}
    with mock_http(lambda r: json_response({})) as calls:
        run(make_executor(cfg, {'api_key': 'k'}).execute({'n': 'x'}, {}))
    body = json.loads(calls[0].content)
    assert body['n'] == 'x' and body['same'] == 'x' and body['at'].endswith('Z')


def test_e3_body_jinja_empty_render_sends_no_body():
    cfg = {'service_name': 's', 'base_url': 'https://h', 'endpoint_template': '/x',
           'request_config': {'method': 'POST', 'body_jinja': '{% if false %}{}{% endif %}  '}}
    with mock_http(lambda r: json_response({})) as calls:
        result = run(make_executor(cfg, {'api_key': 'k'}).execute({'a': 1}, {}))
    assert result['success'] is True and calls[0].content == b''


def test_e3_body_jinja_invalid_json_error_has_position_and_excerpt():
    cfg = {'service_name': 's', 'base_url': 'https://h', 'endpoint_template': '/x',
           'request_config': {'method': 'POST', 'body_jinja': '{"a": {{ a }} }'}}
    with mock_http(lambda r: json_response({})) as calls:
        result = run(make_executor(cfg, {'api_key': 'k'}).execute({'a': 'not-json'}, {}))
    assert result['error'] is True and calls == []
    assert 'body_jinja' in result['message'] and 'column' in result['message']
    assert '{"a": not-json }' in result['message']


def test_e3_query_jinja_csv_list_and_drops_empty():
    cfg = {'service_name': 'getOrders', 'base_url': 'https://sellingpartnerapi-eu.amazon.com',
           'endpoint_template': '/orders/v0/orders',
           'request_config': {
               'method': 'GET',
               'query_params_template': {'MaxResultsPerPage': '{{page_size}}'},
               'query_jinja': '{"MarketplaceIds": {{ auth.marketplace_id | csv_list | tojson }}, '
                              '"CreatedAfter": {{ created_after | iso8601 | tojson }}, '
                              '"NextToken": {{ next_token | tojson }}, "OrderStatuses": ""}',
               'query_list_format': 'csv'}}
    creds = {'access_token': 'Atza', 'marketplace_id': 'A21TJRUUN4KGV, A1F83G8C2ARO7P'}
    ex = make_executor(cfg, creds, {'access_token_header': 'x-amz-access-token', 'access_token_prefix': ''})
    with mock_http(lambda r: json_response({'payload': {'Orders': []}})) as calls:
        result = run(ex.execute({'page_size': 50, 'created_after': '2026-09-01 10:00:00'}, {}))
    assert result['success'] is True
    q = parse_qs(urlparse(str(calls[0].url)).query)
    assert q == {'MaxResultsPerPage': ['50'], 'MarketplaceIds': ['A21TJRUUN4KGV,A1F83G8C2ARO7P'],
                 'CreatedAfter': ['2026-09-01T10:00:00Z']}
    assert calls[0].headers['x-amz-access-token'] == 'Atza'


def test_e3_query_jinja_lists_repeat_by_default():
    cfg = {'service_name': 's', 'base_url': 'https://h', 'endpoint_template': '/x',
           'request_config': {'method': 'GET', 'query_jinja': '{"id": ["a", "b"]}'}}
    with mock_http(lambda r: json_response({})) as calls:
        run(make_executor(cfg, {'api_key': 'k'}).execute({}, {}))
    assert parse_qs(urlparse(str(calls[0].url)).query) == {'id': ['a', 'b']}


# ---------------------------------------------------------------------------
# E4 - Jinja response mapping
# ---------------------------------------------------------------------------

_SP_ORDERS = {'payload': {'Orders': [
    {'AmazonOrderId': '171-1', 'PurchaseDate': '2026-09-29T08:00:00Z', 'OrderStatus': 'Unshipped',
     'OrderTotal': {'Amount': '1299.5', 'CurrencyCode': 'INR'}}], 'NextToken': 'NT'}}

_ORDERS_OUTPUT = (
    '{"orders": [{% for o in response.payload.Orders %}{"channel_order_id": {{ o.AmazonOrderId | tojson }}, '
    '"placed_at": {{ o.PurchaseDate | iso8601 | tojson }}, "total": {{ o.OrderTotal.Amount | money | tojson }}, '
    '"page_size": {{ params.page_size | tojson }}}{% if not loop.last %},{% endif %}{% endfor %}], '
    '"next_cursor": {{ response.payload.NextToken | tojson }}, "http": {{ status_code }}, '
    '"rid": {{ headers["x-amzn-requestid"] | tojson }}}'
)


def test_e4_output_jinja_replaces_data_and_keeps_outer_shape():
    cfg = {'service_name': 'list_orders', 'base_url': 'https://h', 'endpoint_template': '/orders',
           'request_config': {'method': 'GET'}, 'response_config': {'output_jinja': _ORDERS_OUTPUT}}
    with mock_http(lambda r: json_response(_SP_ORDERS, headers={'X-Amzn-RequestId': 'rq-1'})):
        result = run(make_executor(cfg, {'api_key': 'k'}).execute({'page_size': 10}, {}))
    assert set(result.keys()) == {'data', 'status', 'headers', 'success'}
    assert result['success'] is True and result['status'] == 200
    assert result['data'] == {'orders': [{'channel_order_id': '171-1', 'placed_at': '2026-09-29T08:00:00Z',
                                          'total': '1299.50', 'page_size': 10}],
                              'next_cursor': 'NT', 'http': 200, 'rid': 'rq-1'}


def test_e4_keep_raw():
    cfg = {'service_name': 's', 'base_url': 'https://h', 'endpoint_template': '/o', 'request_config': {'method': 'GET'},
           'response_config': {'output_jinja': '{"count": {{ response.payload.Orders | length }}}', 'keep_raw': True}}
    with mock_http(lambda r: json_response(_SP_ORDERS)):
        result = run(make_executor(cfg, {'api_key': 'k'}).execute({}, {}))
    assert result['data'] == {'count': 1, 'raw': _SP_ORDERS}


def test_e4_output_jinja_failure_fails_the_call_with_excerpt():
    cfg = {'service_name': 's', 'base_url': 'https://h', 'endpoint_template': '/o', 'request_config': {'method': 'GET'},
           'response_config': {'output_jinja': '{"x": {{ response.payload.Orders[0].AmazonOrderId }} }'}}
    with mock_http(lambda r: json_response(_SP_ORDERS)):
        result = run(make_executor(cfg, {'api_key': 'k'}).execute({}, {}))
    assert result['error'] is True and result['success'] is False
    assert 'output_jinja' in result['message'] and '171-1' in result['message']
    assert 'Response starts' in result['message']


def test_e4_success_jinja_false_on_200_is_failure_with_error_jinja_message():
    shopify = {'data': {'fulfillmentCreate': {'fulfillment': None,
                                              'userErrors': [{'field': ['trackingNumber'], 'message': 'is invalid'}]}}}
    cfg = {'service_name': 'ship', 'base_url': 'https://h', 'endpoint_template': '/graphql.json',
           'request_config': {'method': 'POST', 'body_jinja': '{"query": "mutation"}'},
           'response_config': {
               'success_jinja': '{{ (response.errors | default([]) | length == 0) and '
                                '(response.data.fulfillmentCreate.userErrors | default([]) | length == 0) }}',
               'error_jinja': '{"message": {{ (response.data.fulfillmentCreate.userErrors | map(attribute="message") '
                              '| join("; ")) | tojson }}}',
               'output_jinja': '{"ok": true}'}}
    with mock_http(lambda r: json_response(shopify)):
        result = run(make_executor(cfg, {'api_key': 'k'}).execute({}, {}))
    assert result['error'] is True and result['success'] is False
    assert result['message'] == 'is invalid'
    assert result['status_code'] == 200


def test_e4_success_jinja_true_then_output():
    cfg = {'service_name': 's', 'base_url': 'https://h', 'endpoint_template': '/g', 'request_config': {'method': 'GET'},
           'response_config': {'success_jinja': '{{ response.errors is not defined }}', 'output_jinja': '{"ok": true}'}}
    with mock_http(lambda r: json_response({'data': {}})):
        result = run(make_executor(cfg, {'api_key': 'k'}).execute({}, {}))
    assert result['success'] is True and result['data'] == {'ok': True}


def test_e4_error_jinja_on_http_failure():
    cfg = {'service_name': 's', 'base_url': 'https://h', 'endpoint_template': '/o', 'request_config': {'method': 'GET'},
           'response_config': {'error_jinja': '{"message": {{ (response.errors[0].code ~ ": " ~ response.errors[0].message) | tojson }}}',
                               'output_jinja': '{"never": true}'}}
    body = {'errors': [{'code': 'InvalidInput', 'message': 'Invalid MarketplaceId'}]}
    with mock_http(lambda r: json_response(body, status=400)):
        result = run(make_executor(cfg, {'api_key': 'k'}).execute({}, {}))
    assert result['error'] is True
    assert result['message'] == 'InvalidInput: Invalid MarketplaceId'


# ---------------------------------------------------------------------------
# E5 - no-network canonical stub
# ---------------------------------------------------------------------------

def test_e5_no_request_stub_makes_no_http_call():
    cfg = {'service_name': 'cancel_order',
           'request_config': {'no_request': True},
           'response_config': {'output_jinja': '{"ok": true, "supported": false, '
                                               '"message": {{ ("Cancel not supported for " ~ params.order_id) | tojson }}}'}}
    with mock_http(lambda r: (_ for _ in ()).throw(AssertionError('HTTP call made'))) as calls:
        result = run(make_executor(cfg, {'access_token': 't'}).execute({'order_id': 'O-9'}, {}))
    assert calls == []
    assert result['success'] is True and result['status'] == 200
    assert result['data'] == {'ok': True, 'supported': False, 'message': 'Cancel not supported for O-9'}


# ---------------------------------------------------------------------------
# backwards compatibility - no new keys
# ---------------------------------------------------------------------------

def test_legacy_body_template_and_result_unchanged():
    cfg = {'service_name': 's', 'base_url': 'https://h/', 'endpoint_template': '/items/{{id}}',
           'request_config': {'method': 'POST', 'body_template': {'name': '{{name}}'},
                              'headers': {'Content-Type': 'application/json'}}}
    with mock_http(lambda r: json_response({'id': 1})) as calls:
        result = run(make_executor(cfg, {'access_token': 'tok'}).execute({'id': '7', 'name': 'n'}, {}))
    assert result == {'data': {'id': 1}, 'status': 200, 'headers': result['headers'], 'success': True}
    assert str(calls[0].url) == 'https://h/items/7'
    assert json.loads(calls[0].content) == {'name': 'n'}
    assert calls[0].headers['Authorization'] == 'Bearer tok'


# ---------------------------------------------------------------------------
# filters
# ---------------------------------------------------------------------------

def test_filters():
    f = FILTERS
    assert f['tojson']({'city': 'Pune', 'name': 'Café ₹'}) == '{"city": "Pune", "name": "Café ₹"}'
    assert f['to_float'](None) == 0.0 and f['to_float']('') == 0.0 and f['to_float']('1,234.5') == 1234.5
    assert f['to_float']('abc', 1.5) == 1.5
    assert f['to_int']('3.0') == 3 and f['to_int'](None, 7) == 7
    assert f['iso8601']('2026-09-30T10:00:00+05:30') == '2026-09-30T04:30:00Z'
    assert f['iso8601']('2026-09-30') == '2026-09-30T00:00:00Z'
    assert f['iso8601'](1790000000) == f['iso8601'](1790000000000) == '2026-09-21T14:13:20Z'
    assert f['iso8601']('') is None and f['iso8601']('garbage') == 'garbage'
    assert f['money'](12.5) == '12.50' and f['money']('2.005') == '2.01' and f['money'](None) == '0.00'
    assert f['from_json']('{"color": "red"}') == {'color': 'red'}
    assert f['from_json']('') == {} and f['from_json'](None, []) == [] and f['from_json']('{bad') == {}
    assert f['from_json']([1]) == [1]
    assert f['csv_list']('a.jpg, b.jpg,, ') == ['a.jpg', 'b.jpg'] and f['csv_list'](['x']) == ['x']
    assert f['csv_list'](None) == []
    # in a template, undefined values stay null-safe
    assert render_json('{"v": {{ missing.deep.path | tojson }}, "n": {{ missing | to_float }}}', {}, 't') == \
        {'v': None, 'n': 0.0}


def test_sandbox_blocks_python_internals():
    # Underscore attributes are unsafe in the sandbox: they resolve to undefined...
    assert render_json('{"c": {{ "".__class__ | tojson }}}', {}, 't') == {'c': None}
    # ...and calling through them fails the render instead of executing anything.
    try:
        render_json('{{ "".__class__.__mro__[1].__subclasses__() }}', {}, 't')
        raise AssertionError('sandbox should refuse')
    except TemplateRenderError as e:
        assert 't' in str(e)


# ---------------------------------------------------------------------------
# webhook signature
# ---------------------------------------------------------------------------

def test_webhook_signature_shopify_base64():
    body = b'{"id": 820982911946154508, "email": "jon@example.com"}'
    secret = 'shpss_secret'
    good = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    cfg = {'header': 'X-Shopify-Hmac-Sha256', 'algorithm': 'sha256', 'encoding': 'base64',
           'secret_field': 'client_secret'}
    headers = httpx.Headers({'X-Shopify-Hmac-Sha256': good})
    assert verify_body_signature(body, headers, cfg, {'client_secret': secret}) == (True, 'ok')
    assert verify_body_signature(body + b' ', headers, cfg, {'client_secret': secret})[0] is False
    assert 'client_secret' in verify_body_signature(body, headers, cfg, {})[1]
    assert 'missing signature header' in verify_body_signature(body, httpx.Headers({}), cfg,
                                                               {'client_secret': secret})[1]


def test_webhook_signature_config_precedence():
    app_cfg = {'signature': {'header': 'A'}}
    assert get_signature_config({'signature': {'header': 'E'}}, app_cfg) == {'header': 'E'}
    assert get_signature_config(json.dumps({}), json.dumps(app_cfg)) == {'header': 'A'}
    assert get_signature_config(None, {'verification_method': 'hmac'}) is None


# ---------------------------------------------------------------------------
# seed validation accepts the new keys
# ---------------------------------------------------------------------------

def test_seed_validator_accepts_new_keys():
    from mcp_server.validators.schema_validator import SchemaValidator
    seed = {
        'key': 'shopify_test', 'version': '1.0.0',
        'application': {
            'app_name': 'Shopify Test', 'description': 'x', 'category': 'Integration',
            'app_type': 'api', 'version': '1.0.0',
            'base_url': 'https://{{auth.shop_domain}}/admin/api/2026-07', 'auth_type': 'oauth2',
            'auth_config': {'authorization_url': 'https://{{auth.shop_domain}}/admin/oauth/authorize',
                            'token_url': 'https://{{auth.shop_domain}}/admin/oauth/access_token',
                            'grant_type': 'client_credentials',
                            'access_token_header': 'X-Shopify-Access-Token', 'access_token_prefix': '',
                            'token_request': {'method': 'POST', 'params_in': 'body', 'extra_params': {}}},
            'webhook_config': {'signature': {'header': 'X-Shopify-Hmac-Sha256', 'algorithm': 'sha256',
                                             'encoding': 'base64', 'secret_field': 'client_secret'}},
        },
        'services': [{
            'service_name': 'list_orders', 'display_name': 'List orders', 'service_type': 'api_call',
            'description': 'List orders', 'endpoint_template': '/graphql.json',
            'request_config': {'method': 'POST', 'body_jinja': '{"query": "q"}', 'query_jinja': '{}',
                               'query_list_format': 'csv', 'encode_path_params': True, 'no_request': False},
            'response_config': {'output_jinja': '{}', 'error_jinja': '{}', 'success_jinja': 'true', 'keep_raw': True},
            'parameter_schema': {'type': 'object', 'properties': {}},
            'output_schema': {'type': 'object', 'properties': {}},
        }],
        'events': [],
    }
    result = SchemaValidator().validate_seed_application(seed)
    assert result['valid'], result['errors']


# ---------------------------------------------------------------------------
# standalone runner
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import logging
    import traceback
    logging.basicConfig(level=logging.CRITICAL)
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith('test_') and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
