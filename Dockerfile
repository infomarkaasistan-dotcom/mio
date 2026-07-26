# MIO Executive OS — Production Hardening #7 (deployment artefaktı).
# Çekirdek STDLIB-ONLY: harici çalışma-zamanı bağımlılığı YOK → kurulum adımı gerekmez.
# Bu imaj, MIO runtime'ını gömen bir ops/monitoring probe'u paketler. MIO'nun dahili HTTP
# sunucusu YOKTUR (gömülebilir runtime); gerçek servis/API katmanı ayrı bir çıktıdır (bkz. DEPLOYMENT.md).

FROM python:3.12-slim

WORKDIR /app
COPY mio_core/ /app/mio_core/
COPY pyproject.toml /app/

# Kalıcı state için workspace hacmi (SQLite domain depoları + WAL)
ENV MIO_WORKSPACE=/data/mio
ENV MIO_HTTP_HOST=0.0.0.0
ENV MIO_HTTP_PORT=8080
VOLUME ["/data"]
EXPOSE 8080

# Container sağlık kontrolü: readiness probe. Hazır değilse exit 1 → orkestratör görür.
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -m mio_core readiness --workspace "$MIO_WORKSPACE" > /dev/null || exit 1

# Varsayılan: readiness probe. HTTP API için:  docker run ... serve   (stdlib http.server, framework yok)
# metrics/health/domains/call komutları da geçilebilir; interaktif kabuk için: docker run -it ... shell
ENTRYPOINT ["python", "-m", "mio_core"]
CMD ["readiness"]
