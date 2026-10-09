FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-devel

ARG RFDETR_VERSION=1.11.2

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "rfdetr[train]==${RFDETR_VERSION}" \
    "torch==2.8.0" "torchvision==0.23.0" pycocotools \
    && python -c "from rfdetr import RFDETRNano; from rfdetr.training.trainer import build_trainer"

WORKDIR /workspace

CMD ["bash"]
