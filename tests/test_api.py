import pytest
from django.test import Client
from unittest.mock import patch

@pytest.mark.django_db
def test_health():
    r=Client().get('/health/')
    assert r.status_code==200
    assert r.json()['status']=='ok'

@pytest.mark.django_db
def test_missing_locations():
    r=Client().get('/api/v1/route-fuel/')
    assert r.status_code==400
    assert 'required' in r.json()['error']
