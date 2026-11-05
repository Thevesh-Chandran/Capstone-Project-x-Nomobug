FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements-reporting.txt requirements-collector.txt /app/
RUN python -m pip install --no-cache-dir -r requirements-collector.txt \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin cp2 \
    && mkdir -p /app/outputs \
    && chown cp2:cp2 /app/outputs

# Copy only the modules called by this job. The local model collector and
# historical scratch programs are outside the image.
COPY --chown=cp2:cp2 \
    scripts/cp2_reporting_release.py \
    scripts/publish_return_risk_predictors.py \
    scripts/publish_prediction_tables.py \
    scripts/callback_live_features.py \
    scripts/cp2_collection_policy.py \
    scripts/compare_callback_candidates_v2.py \
    scripts/benchmark_warranty_models.py \
    scripts/freeze_callback_prospective.py \
    scripts/refresh_callback_validation.py \
    scripts/compare_callback_blind_spots.py \
    scripts/compare_flood_models.py \
    scripts/callback_evaluation.py \
    scripts/warranty_validation_splits.py \
    scripts/cp2_pipeline.py \
    scripts/profile_b2b_sales_payments.py \
    scripts/load_calendar_bronze.py \
    scripts/operational_bronze_core.py \
    scripts/operational_source_contracts.py \
    scripts/prospects_source_contract.py \
    scripts/load_payment_date_serials.py \
    scripts/validate_business_kpis.py \
    scripts/calendar_appointment_policy.py \
    scripts/service_programme_policy.py \
    scripts/release_business_analytics.py \
    scripts/cp2_geocoding.py \
    scripts/pilot_geoapify_calendar.py \
    scripts/inspect_calendar_address_blocks.py \
    scripts/inspect_weather_location_readiness.py \
    /app/scripts/
COPY --chown=cp2:cp2 dbt /app/dbt
COPY --chown=cp2:cp2 webapp /app/webapp
COPY --chown=cp2:cp2 config/cp2_team_coverage.json config/cp2_model_current.json config/cp2_live_feature_contract.json config/cp2_cloud_artifacts.json config/cp2_october10_cohort.json /app/config/
COPY --chown=cp2:cp2 data/processed/boundaries/dosm_districts.geojson /app/data/processed/boundaries/dosm_districts.geojson

USER 10001:10001
CMD ["python", "-m", "scripts.cp2_reporting_release", "run"]
