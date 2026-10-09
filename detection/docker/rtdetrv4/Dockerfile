FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel

ARG RTDETRV4_COMMIT=55fefaaed7efe2a5f72d0a18fd4e05965e35c292
ARG DINOV3_COMMIT=6876159a11b4df116f30f667f8c9888617df0751

RUN apt-get update && apt-get install -y --no-install-recommends \
    git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/RT-DETRs/RT-DETRv4.git /opt/rtdetrv4 \
    && git -C /opt/rtdetrv4 checkout --detach "${RTDETRV4_COMMIT}" \
    && git clone https://github.com/facebookresearch/dinov3.git /opt/dinov3 \
    && git -C /opt/dinov3 checkout --detach "${DINOV3_COMMIT}" \
    && pip install --no-cache-dir \
       -r /opt/rtdetrv4/requirements.txt -r /opt/dinov3/requirements.txt \
       "torch==2.5.1" "torchvision==0.20.1" "transformers==4.49.0" matplotlib \
    && python /opt/rtdetrv4/train.py --help \
    && PYTHONPATH=/opt/dinov3 python -c "import hubconf; assert callable(hubconf.dinov3_vitb16)"

WORKDIR /workspace

CMD ["bash"]
