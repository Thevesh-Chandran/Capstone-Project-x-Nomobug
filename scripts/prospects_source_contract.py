"""Small reusable guard: positional SQL must not run against rearranged headers."""
EXPECTED_HEADERS = [
    'No', 'NO TELEFON', 'PLATFORM (Ads / Website)', 'BOOKING', 'CAN I KNOW MORE',
    'RESIDENTIAL/BUSINESS', 'GPC / ANAI ANAI', 'STATUS OPEN / CLOSED', 'PIC',
    'PAYMENT LINK SENT (PAID / SENT)', 'CATEGORY', 'REMARK', 'ENGAGE',
    '1st F/UP', '2nd F/UP', '3rd F/UP', '4th F/UP', '5th F/UP',
    '', '', '', '', '', '',
]


def validate_headers(headers):
    normalized = [' '.join(header.split()) for header in headers]
    if normalized != EXPECTED_HEADERS:
        raise SystemExit('Source header layout changed. Stop for mapping review; no upload or Silver build.')
