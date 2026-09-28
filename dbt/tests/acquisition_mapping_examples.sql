-- Synthetic examples exercise the actual macro used by the model.
with examples as (
    select * from unnest([
        struct('B27' as label, 'BUSINESS_AD' as expected),
        ('ADS78', 'REGULAR_AD'), ('A97', 'REGULAR_AD'), ('CA 6', 'REGULAR_AD'),
        ('ADS', 'UNSPECIFIED_AD'), ('NA', 'UNKNOWN'), ('', 'MISSING'),
        ('JESS', 'UNRESOLVED'), ('SEMUT #7', 'UNRESOLVED'),
        ('BLAH', 'UNRESOLVED'), ('ADS?', 'UNRESOLVED'),
        ('FB', 'FACEBOOK'), ('WEBSIITE', 'WEBSITE'), ('REFERAL', 'REFERRAL')
    ])
), checked as (
    select *, {{ acquisition_group('label') }} as actual from examples
)
select * from checked where actual != expected
