import math
import os
import threading

import librosa
import numpy as np
import torch
import torchaudio


def trim_silence(audio, sr, keep_left_time=0.05, keep_right_time=0.22, hop_size=240):
    _, index = librosa.effects.trim(audio, top_db=20, frame_length=512, hop_length=128)
    num_frames = int(math.ceil((index[1] - index[0]) / hop_size))  # 300

    left_sil_samples = int(keep_left_time * sr)

    start_idx = index[0] - left_sil_samples
    trim_wav = audio

    if start_idx > 0:
        trim_wav = trim_wav[start_idx:]
    else:
        trim_wav = np.pad(trim_wav, (abs(start_idx), 0), mode="constant", constant_values=0.0)
    wav_len = len(trim_wav)
    out_len = int(num_frames * hop_size + (keep_left_time + keep_right_time) * sr)

    if out_len < wav_len:
        trim_wav = trim_wav[:out_len]
    else:
        trim_wav = np.pad(trim_wav, (0, (out_len - wav_len)), mode="constant", constant_values=0.0)
    return trim_wav


def resample_audio(wav, original_sample_rate, target_sample_rate):
    if original_sample_rate != target_sample_rate:
        assert original_sample_rate > target_sample_rate, "wav sample rate {} must be greater than {}".format(
            original_sample_rate, target_sample_rate
        )
        wav = torchaudio.transforms.Resample(orig_freq=original_sample_rate, new_freq=target_sample_rate)(wav)
    return wav


def energy_norm_fn(wav):
    if type(wav) is np.ndarray:
        max_data = np.max(np.abs(wav))
        wav = wav / max(max_data, 0.01) * 0.999
    else:
        max_data = torch.max(torch.abs(wav))
        wav = wav / max(max_data, 0.01) * 0.999
    return wav


def get_audio_tokens(audio_tokens: str) -> list[int]:
    audio_tokens = audio_tokens.split("><audio_")
    audio_tokens = [int(token.replace("<audio_", "").replace(">", "")) + 65536 for token in audio_tokens]
    return audio_tokens


def load_audio(audio_path: str):
    audio_wav, sr = torchaudio.load(audio_path)
    audio_wav = audio_wav.mean(dim=0, keepdim=True)
    return audio_wav, sr


# load optimus_ths for flash attention, make sure LD_LIBRARY_PATH has `nvidia/cuda_nvrtc/lib`
# if not, please manually set LD_LIBRARY_PATH=xxx/python3.10/site-packages/nvidia/cuda_nvrtc/lib
def load_optimus_ths_lib(libpath):
    if not hasattr(load_optimus_ths_lib, "lock"):
        load_optimus_ths_lib.lock = threading.Lock()
    if not hasattr(load_optimus_ths_lib, "success"):
        load_optimus_ths_lib.success = False

    with load_optimus_ths_lib.lock:
        if load_optimus_ths_lib.success:
            return load_optimus_ths_lib.success

        try:
            if torch.__version__ >= "2.5":
                torch.ops.load_library(
                    os.path.join(libpath, "liboptimus_ths-torch2.5-cu124.cpython-310-x86_64-linux-gnu.so")
                )
            elif torch.__version__ >= "2.3":
                torch.ops.load_library(
                    os.path.join(libpath, "liboptimus_ths-torch2.3-cu121.cpython-310-x86_64-linux-gnu.so")
                )
            elif torch.__version__ >= "2.2":
                torch.ops.load_library(
                    os.path.join(libpath, "liboptimus_ths-torch2.2-cu121.cpython-310-x86_64-linux-gnu.so")
                )
            else:
                raise RuntimeError("Unsupported torch version")
            print("Load optimus_ths successfully and flash attn would be enabled")
            load_optimus_ths_lib.success = True
        except Exception as err:
            print(f"Fail to load optimus_ths and flash attn is disabled: {err}")
            load_optimus_ths_lib.success = False

        return load_optimus_ths_lib.success
