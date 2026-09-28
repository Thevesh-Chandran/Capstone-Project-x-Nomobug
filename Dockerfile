FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements-reporting.txt /app/
RUN python -m pip install --no-cache-dir -r requirements-reporting.txt \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin cp2 \
    && mkdir -p /app/outputs \
    && chown cp2:cp2 /app/outputs

# Copy only the modules called by this job. The local model collector and
# historical scratch programs are outside the image.
COPY --chown=cp2:cp2 \
    scripts/cp2_reporting_release.py \
    scripts/cp2_pipeline.py \
    scripts/profile_b2b_sales_payments.py \
    scripts/load_calendar_bronze.py \
    scripts/operational_bronze_core.py \
    scripts/operational_source_contracts.py \
    scripts/prospects_source_contract.py \
    scripts/load_payment_date_serials.py \
    scripts/validate_business_kpis.py \
    /app/scripts/
COPY --chown=cp2:cp2 dbt /app/dbt

USER 10001:10001
CMD ["python", "-m", "scripts.cp2_reporting_release", "run"]
