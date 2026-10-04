# AWS Lambda base image for Python 3.12 (includes the Lambda runtime interface).
FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir . && rm -rf src pyproject.toml build

# One image, one entry point; the event's "source" field picks the handler.
CMD ["bikeshare_ingest.handler.handler"]
