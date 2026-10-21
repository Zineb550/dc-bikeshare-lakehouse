FROM astrocrpublic.azurecr.io/runtime:3.3-8

# dbt runs in its own virtualenv on Python 3.12: Airflow's Python (3.14) has no wheel for
# a pinned dbt dependency (mmh3 < 4.2), and the image has no compiler. uv fetches a
# standalone Python 3.12 into the project folder; Airflow itself is untouched.
ENV UV_PYTHON_INSTALL_DIR=/usr/local/airflow/.python
RUN python -m venv /tmp/uv \
    && /tmp/uv/bin/pip install --no-cache-dir uv \
    && /tmp/uv/bin/uv venv --python 3.12 dbt_venv \
    && /tmp/uv/bin/uv pip install --no-cache --python dbt_venv/bin/python -r dbt/requirements.txt \
    && rm -rf /tmp/uv \
    && dbt_venv/bin/dbt --version
