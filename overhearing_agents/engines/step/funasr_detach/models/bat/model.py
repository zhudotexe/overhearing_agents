#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# Copyright FunASR (https://github.com/alibaba-damo-academy/FunASR). All Rights Reserved.
#  MIT License  (https://opensource.org/licenses/MIT)

import logging
import time
from contextlib import contextmanager
from distutils.version import LooseVersion
from typing import Dict, Optional, Tuple

import torch
from funasr_detach.losses.label_smoothing_loss import LabelSmoothingLoss
from funasr_detach.models.transducer.beam_search_transducer import BeamSearchTransducer
from funasr_detach.models.transducer.model import Transducer
from funasr_detach.models.transformer.scorers.ctc import CTCPrefixScorer
from funasr_detach.models.transformer.scorers.length_bonus import LengthBonus
from funasr_detach.models.transformer.utils.nets_utils import get_transducer_task_io
from funasr_detach.register import tables
from funasr_detach.train_utils.device_funcs import force_gatherable
from funasr_detach.utils import postprocess_utils
from funasr_detach.utils.datadir_writer import DatadirWriter
from funasr_detach.utils.load_utils import extract_fbank, load_audio_text_image_video

if LooseVersion(torch.__version__) >= LooseVersion("1.6.0"):
    from torch.cuda.amp import autocast
else:
    # Nothing to do if torch<1.6.0
    @contextmanager
    def autocast(enabled=True):
        yield


@tables.register("model_classes", "BAT")  # TODO: BAT training
class BAT(Transducer):
    pass
