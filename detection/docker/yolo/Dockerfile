FROM ultralytics/ultralytics:8.4.152

COPY scripts/phase1/requirements.txt /tmp/phase1-requirements.txt
RUN pip install --no-cache-dir -r /tmp/phase1-requirements.txt && pip check

WORKDIR /workspace

CMD ["bash"]
