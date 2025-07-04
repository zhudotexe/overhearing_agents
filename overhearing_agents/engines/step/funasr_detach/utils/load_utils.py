import io
import os

import numpy as np
import torch
import torchaudio
from torch.nn.utils.rnn import pad_sequence

try:
    from funasr_detach.download.file import download_from_url
except:
    print("urllib is not installed, if you infer from url, please install it first.")


def load_audio_text_image_video(
    data_or_path_or_list, fs: int = 16000, audio_fs: int = 16000, data_type="sound", tokenizer=None, **kwargs
):
    if isinstance(data_or_path_or_list, (list, tuple)):
        if data_type is not None and isinstance(data_type, (list, tuple)):

            data_types = [data_type] * len(data_or_path_or_list)
            data_or_path_or_list_ret = [[] for d in data_type]
            for i, (data_type_i, data_or_path_or_list_i) in enumerate(zip(data_types, data_or_path_or_list)):

                for j, (data_type_j, data_or_path_or_list_j) in enumerate(zip(data_type_i, data_or_path_or_list_i)):

                    data_or_path_or_list_j = load_audio_text_image_video(
                        data_or_path_or_list_j,
                        fs=fs,
                        audio_fs=audio_fs,
                        data_type=data_type_j,
                        tokenizer=tokenizer,
                        **kwargs,
                    )
                    data_or_path_or_list_ret[j].append(data_or_path_or_list_j)

            return data_or_path_or_list_ret
        else:
            return [
                load_audio_text_image_video(audio, fs=fs, audio_fs=audio_fs, data_type=data_type, **kwargs)
                for audio in data_or_path_or_list
            ]

    if isinstance(data_or_path_or_list, str) and data_or_path_or_list.startswith("http"):  # download url to local file
        data_or_path_or_list = download_from_url(data_or_path_or_list)

    if isinstance(data_or_path_or_list, io.BytesIO):
        data_or_path_or_list, audio_fs = torchaudio.load(data_or_path_or_list)
        if kwargs.get("reduce_channels", True):
            data_or_path_or_list = data_or_path_or_list.mean(0)
    elif isinstance(data_or_path_or_list, str) and os.path.exists(data_or_path_or_list):  # local file
        if data_type is None or data_type == "sound":
            data_or_path_or_list, audio_fs = torchaudio.load(data_or_path_or_list)
            if kwargs.get("reduce_channels", True):
                data_or_path_or_list = data_or_path_or_list.mean(0)
        elif data_type == "text" and tokenizer is not None:
            data_or_path_or_list = tokenizer.encode(data_or_path_or_list)
        elif data_type == "image":  # undo
            pass
        elif data_type == "video":  # undo
            pass

        # if data_in is a file or url, set is_final=True
        if "cache" in kwargs:
            kwargs["cache"]["is_final"] = True
            kwargs["cache"]["is_streaming_input"] = False
    elif isinstance(data_or_path_or_list, str) and data_type == "text" and tokenizer is not None:
        data_or_path_or_list = tokenizer.encode(data_or_path_or_list)
    elif isinstance(data_or_path_or_list, np.ndarray):  # audio sample point
        data_or_path_or_list = torch.from_numpy(data_or_path_or_list).squeeze()  # [n_samples,]
    else:
        pass
        # print(f"unsupport data type: {data_or_path_or_list}, return raw data")

    if audio_fs != fs and data_type != "text":
        resampler = torchaudio.transforms.Resample(audio_fs, fs)
        data_or_path_or_list = resampler(data_or_path_or_list[None, :])[0, :]
    return data_or_path_or_list


def load_bytes(input):
    middle_data = np.frombuffer(input, dtype=np.int16)
    middle_data = np.asarray(middle_data)
    if middle_data.dtype.kind not in "iu":
        raise TypeError("'middle_data' must be an array of integers")
    dtype = np.dtype("float32")
    if dtype.kind != "f":
        raise TypeError("'dtype' must be a floating point type")

    i = np.iinfo(middle_data.dtype)
    abs_max = 2 ** (i.bits - 1)
    offset = i.min + abs_max
    array = np.frombuffer((middle_data.astype(dtype) - offset) / abs_max, dtype=np.float32)
    return array


def extract_fbank(data, data_len=None, data_type: str = "sound", frontend=None, **kwargs):
    # import pdb;
    # pdb.set_trace()
    if isinstance(data, np.ndarray):
        data = torch.from_numpy(data)
        if len(data.shape) < 2:
            data = data[None, :]  # data: [batch, N]
        data_len = [data.shape[1]] if data_len is None else data_len
    elif isinstance(data, torch.Tensor):
        if len(data.shape) < 2:
            data = data[None, :]  # data: [batch, N]
        data_len = [data.shape[1]] if data_len is None else data_len
    elif isinstance(data, (list, tuple)):
        data_list, data_len = [], []
        for data_i in data:
            if isinstance(data_i, np.ndarray):
                data_i = torch.from_numpy(data_i)
            data_list.append(data_i)
            data_len.append(data_i.shape[0])
        data = pad_sequence(data_list, batch_first=True)  # data: [batch, N]
    # import pdb;
    # pdb.set_trace()
    # if data_type == "sound":
    data, data_len = frontend(data, data_len, **kwargs)

    if isinstance(data_len, (list, tuple)):
        data_len = torch.tensor([data_len])
    return data.to(torch.float32), data_len.to(torch.int32)
