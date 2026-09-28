{{ config(tags=['calendar']) }}
-- Synthetic fixtures call the same classification macro as the production
-- model. Reviewed events are regression overrides, not an untouched test set.
with fixtures as (
    select 'sequence_claim' as example, 'GPC 4/3 EXAMPLE' as title,
        'confirmed' as status, 4 as session_current, 3 as session_total,
        'warranty' as expected union all
    select 'complimentary_sequence', 'GPC 5/3 COMPLIMENTARY EXAMPLE', 'confirmed', 5, 3, 'warranty' union all
    select 'explicit_claim', 'GPC WARRANTY CLAIM EXAMPLE', 'confirmed', null, null, 'warranty' union all
    select 'no_warranty', 'GPC 1/1 EXAMPLE (NO WARRANTY)', 'confirmed', 1, 1, 'service' union all
    select 'no_warranty_other', 'NO WARRANTY', 'confirmed', null, null, 'other' union all
    select 'without_warranty', 'GPC 1/3 EXAMPLE WITHOUT WARRANTY', 'confirmed', 1, 3, 'service' union all
    select 'independent_callback', 'NO WARRANTY CALLBACK EXAMPLE', 'confirmed', null, null, 'warranty' union all
    select 'consultation_overrun', 'GPC CONSULTATION 2/1 EXAMPLE', 'confirmed', 2, 1, 'consultation' union all
    select 'inspection_overrun', 'INSPECTION 4/3 EXAMPLE', 'confirmed', 4, 3, 'consultation' union all
    select 'explicit_claim_inspection', 'WARRANTY INSPECTION EXAMPLE', 'confirmed', null, null, 'warranty' union all
    select 'cancelled_claim', 'GPC WARRANTY EXAMPLE', 'cancelled', null, null, 'cancelled' union all
    select 'admin_terms', 'CHECK CONVERSION RATE WARRANTY', 'confirmed', null, null, 'administrative' union all
    select 'complimentary_only', 'GPC COMPLIMENTARY EXAMPLE', 'confirmed', null, null, 'complimentary' union all
    select 'non_claim_word', 'UNCLAIMED PAYMENT', 'confirmed', null, null, 'other'
), actual as (
    select example, expected,
        {{ calendar_event_category('title', 'status', 'session_current', 'session_total') }} as actual
    from fixtures
)
select a.* from actual a where a.actual is distinct from a.expected
