FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel

ARG DFINE_COMMIT=956d1709314c2c6a4df6f34de232054578a7449f

RUN apt-get update && apt-get install -y --no-install-recommends \
    git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Peterande/D-FINE.git /opt/dfine \
    && git -C /opt/dfine checkout --detach "${DFINE_COMMIT}" \
    && pip install --no-cache-dir -r /opt/dfine/requirements.txt \
       "torch==2.5.1" "torchvision==0.20.1" "transformers==4.49.0" matplotlib pycocotools \
    && python -c "import torch, torchvision; from pycocotools.coco import COCO; assert torch.__version__.split('+')[0] == '2.5.1'; assert torchvision.__version__.split('+')[0] == '0.20.1'" \
    && python /opt/dfine/train.py --help

WORKDIR /workspace

COPY scripts/phase1/requirements.txt /tmp/phase1-requirements.txt
RUN pip install --no-cache-dir -r /tmp/phase1-requirements.txt && pip check

CMD ["bash"]
