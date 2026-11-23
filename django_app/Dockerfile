FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m pip check \
    && python -c "from pathlib import Path; import shutil, sysconfig; site=Path(sysconfig.get_paths()['purelib']); [shutil.rmtree(p) if p.is_dir() else p.unlink() for pattern in ('pip','pip-*.dist-info','setuptools','setuptools-*.dist-info','wheel','wheel-*.dist-info') for p in site.glob(pattern)]; [p.unlink() for pattern in ('pip','pip3','pip3.13') for p in Path(sysconfig.get_config_var('BINDIR')).glob(pattern) if p.is_file()]" \
    && groupadd --system --gid 10001 django \
    && useradd --system --uid 10001 --gid django --home-dir /app --no-create-home django

COPY --chown=django:django config/ /app/config/
COPY --chown=django:django accounts/ /app/accounts/
COPY --chown=django:django conversations/ /app/conversations/
COPY --chown=django:django chat/ /app/chat/
COPY --chown=django:django rag_client/ /app/rag_client/
COPY --chown=django:django templates/ /app/templates/
COPY --chown=django:django manage.py startup.py /app/

RUN DJANGO_SECRET_KEY=static-build-only-key DJANGO_DEBUG=0 python manage.py collectstatic --noinput

USER django
EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "135", "--graceful-timeout", "125", "--keep-alive", "2"]
