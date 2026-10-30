from django.test import override_settings


@override_settings(SECURE_SSL_REDIRECT=True)
def test_production_redirects_http_but_allows_container_health_check(client):
    assert client.get('/').status_code == 301
    assert client.get('/health/').status_code == 200
    assert client.get('/', HTTP_X_FORWARDED_PROTO='https').status_code == 200
