"""Conservative review helpers; no customer identity inference or payment splitting."""
import re
from decimal import Decimal


def recorded_returning_client(label):
    # Word boundaries prevent COLD from matching OLD. Mixed campaign labels remain raw.
    return bool(re.search(r'\b(?:OLD|RETURNING)\b', str(label).upper()))


def parse_rm_amount(value):
    text = str(value).strip()
    # Only plain decimals or correctly grouped thousands; no silent text stripping.
    if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?', text):
        return None
    return Decimal(text.replace(',', ''))


def parse_sales_references(value):
    """Parse the WHOLE field; never extract a plausible ID from arbitrary text.

    Numeric shorthand is allowed only after an explicit CUST prefix.
    Returns IDs plus a review status; never returns a partial allocation.
    """
    text = str(value).strip().upper()
    if not text:
        return [], 'missing'
    if not re.fullmatch(r'CUST\s*\d+(?:\s*[,/]\s*(?:CUST\s*)?\d+)*', text):
        return [], 'unrecognized'
    parts = re.split(r'\s*[,/]\s*', text)
    ids = ['CUST' + re.sub(r'^CUST\s*', '', part).strip() for part in parts]
    if len(ids) != len(set(ids)):
        return list(dict.fromkeys(ids)), 'repeated_reference_review'
    return ids, 'combined' if len(ids) > 1 else 'single'
