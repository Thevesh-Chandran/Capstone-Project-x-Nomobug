import runpy
from pathlib import Path
from decimal import Decimal
import pytest

rules = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/sales_payment_rules.py'))

@pytest.mark.parametrize('label', ['OLD', 'old client', 'ADS57 (OLD)', 'RETURNING CUST / TIKTOK ADS'])
def test_returning_signal(label):
    assert rules['recorded_returning_client'](label)

@pytest.mark.parametrize('label', ['', 'B2B COLD', 'ADS78', 'GOLD'])
def test_not_returning_signal(label):
    assert not rules['recorded_returning_client'](label)

@pytest.mark.parametrize('text', ['TESTING', 'Pest Control', '1,2', '', 'RM200', '200+100'])
def test_unsupported_amount_is_not_zero(text):
    assert rules['parse_rm_amount'](text) is None

def test_decimal_amount():
    assert rules['parse_rm_amount']('1,200.50') == Decimal('1200.50')

@pytest.mark.parametrize('text,expected,status', [
    ('CUST417', ['CUST417'], 'single'),
    ('cust 501', ['CUST501'], 'single'),
    ('CUST467, CUST429', ['CUST467', 'CUST429'], 'combined'),
    ('CUST523 / 524', ['CUST523', 'CUST524'], 'combined'),
    ('CUST706 / CUST 707', ['CUST706', 'CUST707'], 'combined'),
    ('CUST001 / 002', ['CUST001', 'CUST002'], 'combined'),
    ('CUST1 / CUST1', ['CUST1'], 'repeated_reference_review'),
    ('CUST417 ( Giro )', [], 'unrecognized'),
    ('60123456789', [], 'unrecognized'),
    ('CUST1 / unknown', [], 'unrecognized'),
    ('CUST1 /', [], 'unrecognized'),
    ('', [], 'missing'),
])
def test_sales_references(text, expected, status):
    assert rules['parse_sales_references'](text) == (expected, status)
