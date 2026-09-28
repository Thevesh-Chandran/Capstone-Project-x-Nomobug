{{ config(tags=['calendar', 'matching']) }}
with examples as (
    select 'Alamat: Unit 2-4, 58000 Kuala Lumpur' as description_text,
        'Unit 2-4, 58000 Kuala Lumpur' as expected union all
    select 'Nama: Example Customer\nAlamat Unit 2-4, 58000 Kuala Lumpur\nPhone: 0123456789',
        'Unit 2-4, 58000 Kuala Lumpur' union all
    select 'Nama: Example Customer Alamat: Jalan Contoh 1, 58000 KL Package: 3x Session',
        'Jalan Contoh 1, 58000 KL' union all
    select 'Addresses: Jalan Contoh 5, 58000 KL', 'Jalan Contoh 5, 58000 KL' union all
    select '*Alamat*: Jalan Contoh 6, 58000 KL', 'Jalan Contoh 6, 58000 KL' union all
    select 'Full Address*: Jalan Contoh 7, 58000 KL', 'Jalan Contoh 7, 58000 KL' union all
    select 'Address. No 3, Jalan Contoh 8, 58000 KL', 'No 3, Jalan Contoh 8, 58000 KL' union all
    select 'Nama: A<br>&nbsp;Alamat: Jalan Contoh 9, 58000 KL',
        'Jalan Contoh 9, 58000 KL' union all
    select concat('Nama: A', chr(160), 'Alamat: Jalan Contoh 10, 58000 KL'),
        'Jalan Contoh 10, 58000 KL' union all
    select 'Example Customer\nno 7 jalan contoh 6/1, Cheras\n0120000000',
        'no 7 jalan contoh 6/1, Cheras' union all
    select 'Example Enterprise\nNo. 9, Jln Contoh 1/2,\n58000 Kuala Lumpur',
        'No. 9, Jln Contoh 1/2,' union all
    select 'Example Customer\n2-14-03,RESIDENSI CONTOH SEKSYEN 13 Shah Alam',
        '2-14-03,RESIDENSI CONTOH SEKSYEN 13 Shah Alam' union all
    select 'Lot 1, Sec 2, Jalan Contoh, 58000 Kuala Lumpur',
        'Lot 1, Sec 2, Jalan Contoh, 58000 Kuala Lumpur' union all
    select 'Phone: 0123456789\nInvoice: inv_12345', null
), actual as (
    select description_text, expected,
        {{ calendar_address_line('description_text') }} as extracted
    from examples
)
select * from actual where extracted is distinct from expected
