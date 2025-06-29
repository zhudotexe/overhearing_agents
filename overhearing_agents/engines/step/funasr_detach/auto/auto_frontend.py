import logging
import time

from funasr_detach.auto.auto_model import prepare_data_iterator
from funasr_detach.download.download_from_hub import download_model
from funasr_detach.register import tables
from funasr_detach.utils.load_utils import extract_fbank, load_audio_text_image_video
from tqdm import tqdm


class AutoFrontend:
    def __init__(self, **kwargs):
        assert "model" in kwargs
        if "model_conf" not in kwargs:
            logging.info("download models from model hub: {}".format(kwargs.get("model_hub", "ms")))
            kwargs = download_model(**kwargs)

        # build frontend
        frontend = kwargs.get("frontend", None)
        if frontend is not None:
            frontend_class = tables.frontend_classes.get(frontend)
            frontend = frontend_class(**kwargs["frontend_conf"])

        self.frontend = frontend
        if "frontend" in kwargs:
            del kwargs["frontend"]
        self.kwargs = kwargs

    def __call__(self, input, input_len=None, kwargs=None, **cfg):

        kwargs = self.kwargs if kwargs is None else kwargs
        kwargs.update(cfg)

        key_list, data_list = prepare_data_iterator(input, input_len=input_len)
        batch_size = kwargs.get("batch_size", 1)
        device = kwargs.get("device", "cpu")
        if device == "cpu":
            batch_size = 1

        meta_data = {}

        result_list = []
        num_samples = len(data_list)
        pbar = tqdm(colour="blue", total=num_samples + 1, dynamic_ncols=True)

        time0 = time.perf_counter()
        for beg_idx in range(0, num_samples, batch_size):
            end_idx = min(num_samples, beg_idx + batch_size)
            data_batch = data_list[beg_idx:end_idx]
            key_batch = key_list[beg_idx:end_idx]

            # extract fbank feats
            time1 = time.perf_counter()
            audio_sample_list = load_audio_text_image_video(
                data_batch, fs=self.frontend.fs, audio_fs=kwargs.get("fs", 16000)
            )
            time2 = time.perf_counter()
            meta_data["load_data"] = f"{time2 - time1:0.3f}"
            speech, speech_lengths = extract_fbank(
                audio_sample_list,
                data_type=kwargs.get("data_type", "sound"),
                frontend=self.frontend,
                **kwargs,
            )
            time3 = time.perf_counter()
            meta_data["extract_feat"] = f"{time3 - time2:0.3f}"
            meta_data["batch_data_time"] = (
                speech_lengths.sum().item() * self.frontend.frame_shift * self.frontend.lfr_n / 1000
            )

            speech.to(device=device), speech_lengths.to(device=device)
            batch = {"input": speech, "input_len": speech_lengths, "key": key_batch}
            result_list.append(batch)

            pbar.update(1)
            description = f"{meta_data}, "
            pbar.set_description(description)

        time_end = time.perf_counter()
        pbar.set_description(f"time escaped total: {time_end - time0:0.3f}")

        return result_list
