import logging
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
from funasr_detach.models.ctc import CTC
from funasr_detach.models.encoder.abs_encoder import AbsEncoder
from funasr_detach.models.scama.chunk_utilis import overlap_chunk
from funasr_detach.models.sond.attention import MultiHeadSelfAttention
from funasr_detach.models.transformer.embedding import SinusoidalPositionEncoder
from funasr_detach.models.transformer.layer_norm import LayerNorm
from funasr_detach.models.transformer.positionwise_feed_forward import PositionwiseFeedForward  # noqa: H301
from funasr_detach.models.transformer.utils.multi_layer_conv import Conv1dLinear, MultiLayeredConv1d
from funasr_detach.models.transformer.utils.nets_utils import make_pad_mask
from funasr_detach.models.transformer.utils.repeat import repeat
from funasr_detach.models.transformer.utils.subsampling import (
    Conv2dSubsampling,
    Conv2dSubsampling2,
    Conv2dSubsampling6,
    Conv2dSubsampling8,
    TooShortUttError,
    check_short_utt,
)


class EncoderLayer(nn.Module):
    def __init__(
        self,
        in_size,
        size,
        self_attn,
        feed_forward,
        dropout_rate,
        normalize_before=True,
        concat_after=False,
        stochastic_depth_rate=0.0,
    ):
        """Construct an EncoderLayer object."""
        super(EncoderLayer, self).__init__()
        self.self_attn = self_attn
        self.feed_forward = feed_forward
        self.norm1 = LayerNorm(in_size)
        self.norm2 = LayerNorm(size)
        self.dropout = nn.Dropout(dropout_rate)
        self.in_size = in_size
        self.size = size
        self.normalize_before = normalize_before
        self.concat_after = concat_after
        if self.concat_after:
            self.concat_linear = nn.Linear(size + size, size)
        self.stochastic_depth_rate = stochastic_depth_rate
        self.dropout_rate = dropout_rate

    def forward(self, x, mask, cache=None, mask_att_chunk_encoder=None):
        """Compute encoded features.

        Args:
            x_input (torch.Tensor): Input tensor (#batch, time, size).
            mask (torch.Tensor): Mask tensor for the input (#batch, time).
            cache (torch.Tensor): Cache tensor of the input (#batch, time - 1, size).

        Returns:
            torch.Tensor: Output tensor (#batch, time, size).
            torch.Tensor: Mask tensor (#batch, time).

        """
        skip_layer = False
        # with stochastic depth, residual connection `x + f(x)` becomes
        # `x <- x + 1 / (1 - p) * f(x)` at training time.
        stoch_layer_coeff = 1.0
        if self.training and self.stochastic_depth_rate > 0:
            skip_layer = torch.rand(1).item() < self.stochastic_depth_rate
            stoch_layer_coeff = 1.0 / (1 - self.stochastic_depth_rate)

        if skip_layer:
            if cache is not None:
                x = torch.cat([cache, x], dim=1)
            return x, mask

        residual = x
        if self.normalize_before:
            x = self.norm1(x)

        if self.concat_after:
            x_concat = torch.cat(
                (
                    x,
                    self.self_attn(x, mask, mask_att_chunk_encoder=mask_att_chunk_encoder),
                ),
                dim=-1,
            )
            if self.in_size == self.size:
                x = residual + stoch_layer_coeff * self.concat_linear(x_concat)
            else:
                x = stoch_layer_coeff * self.concat_linear(x_concat)
        else:
            if self.in_size == self.size:
                x = residual + stoch_layer_coeff * self.dropout(
                    self.self_attn(x, mask, mask_att_chunk_encoder=mask_att_chunk_encoder)
                )
            else:
                x = stoch_layer_coeff * self.dropout(
                    self.self_attn(x, mask, mask_att_chunk_encoder=mask_att_chunk_encoder)
                )
        if not self.normalize_before:
            x = self.norm1(x)

        residual = x
        if self.normalize_before:
            x = self.norm2(x)
        x = residual + stoch_layer_coeff * self.dropout(self.feed_forward(x))
        if not self.normalize_before:
            x = self.norm2(x)

        return x, mask, cache, mask_att_chunk_encoder


class SelfAttentionEncoder(AbsEncoder):
    """
    Author: Speech Lab of DAMO Academy, Alibaba Group
    Self attention encoder in OpenNMT framework
    """

    def __init__(
        self,
        input_size: int,
        output_size: int = 256,
        attention_heads: int = 4,
        linear_units: int = 2048,
        num_blocks: int = 6,
        dropout_rate: float = 0.1,
        positional_dropout_rate: float = 0.1,
        attention_dropout_rate: float = 0.0,
        input_layer: Optional[str] = "conv2d",
        pos_enc_class=SinusoidalPositionEncoder,
        normalize_before: bool = True,
        concat_after: bool = False,
        positionwise_layer_type: str = "linear",
        positionwise_conv_kernel_size: int = 1,
        padding_idx: int = -1,
        interctc_layer_idx: List[int] = [],
        interctc_use_conditioning: bool = False,
        tf2torch_tensor_name_prefix_torch: str = "encoder",
        tf2torch_tensor_name_prefix_tf: str = "seq2seq/encoder",
        out_units=None,
    ):
        super().__init__()
        self._output_size = output_size

        if input_layer == "linear":
            self.embed = torch.nn.Sequential(
                torch.nn.Linear(input_size, output_size),
                torch.nn.LayerNorm(output_size),
                torch.nn.Dropout(dropout_rate),
                torch.nn.ReLU(),
                pos_enc_class(output_size, positional_dropout_rate),
            )
        elif input_layer == "conv2d":
            self.embed = Conv2dSubsampling(input_size, output_size, dropout_rate)
        elif input_layer == "conv2d2":
            self.embed = Conv2dSubsampling2(input_size, output_size, dropout_rate)
        elif input_layer == "conv2d6":
            self.embed = Conv2dSubsampling6(input_size, output_size, dropout_rate)
        elif input_layer == "conv2d8":
            self.embed = Conv2dSubsampling8(input_size, output_size, dropout_rate)
        elif input_layer == "embed":
            self.embed = torch.nn.Sequential(
                torch.nn.Embedding(input_size, output_size, padding_idx=padding_idx),
                SinusoidalPositionEncoder(),
            )
        elif input_layer is None:
            if input_size == output_size:
                self.embed = None
            else:
                self.embed = torch.nn.Linear(input_size, output_size)
        elif input_layer == "pe":
            self.embed = SinusoidalPositionEncoder()
        elif input_layer == "null":
            self.embed = None
        else:
            raise ValueError("unknown input_layer: " + input_layer)
        self.normalize_before = normalize_before
        if positionwise_layer_type == "linear":
            positionwise_layer = PositionwiseFeedForward
            positionwise_layer_args = (
                output_size,
                linear_units,
                dropout_rate,
            )
        elif positionwise_layer_type == "conv1d":
            positionwise_layer = MultiLayeredConv1d
            positionwise_layer_args = (
                output_size,
                linear_units,
                positionwise_conv_kernel_size,
                dropout_rate,
            )
        elif positionwise_layer_type == "conv1d-linear":
            positionwise_layer = Conv1dLinear
            positionwise_layer_args = (
                output_size,
                linear_units,
                positionwise_conv_kernel_size,
                dropout_rate,
            )
        else:
            raise NotImplementedError("Support only linear or conv1d.")

        self.encoders = repeat(
            num_blocks,
            lambda lnum: (
                EncoderLayer(
                    output_size,
                    output_size,
                    MultiHeadSelfAttention(
                        attention_heads,
                        output_size,
                        output_size,
                        attention_dropout_rate,
                    ),
                    positionwise_layer(*positionwise_layer_args),
                    dropout_rate,
                    normalize_before,
                    concat_after,
                )
                if lnum > 0
                else EncoderLayer(
                    input_size,
                    output_size,
                    MultiHeadSelfAttention(
                        attention_heads,
                        (input_size if input_layer == "pe" or input_layer == "null" else output_size),
                        output_size,
                        attention_dropout_rate,
                    ),
                    positionwise_layer(*positionwise_layer_args),
                    dropout_rate,
                    normalize_before,
                    concat_after,
                )
            ),
        )
        if self.normalize_before:
            self.after_norm = LayerNorm(output_size)

        self.interctc_layer_idx = interctc_layer_idx
        if len(interctc_layer_idx) > 0:
            assert 0 < min(interctc_layer_idx) and max(interctc_layer_idx) < num_blocks
        self.interctc_use_conditioning = interctc_use_conditioning
        self.conditioning_layer = None
        self.dropout = nn.Dropout(dropout_rate)
        self.tf2torch_tensor_name_prefix_torch = tf2torch_tensor_name_prefix_torch
        self.tf2torch_tensor_name_prefix_tf = tf2torch_tensor_name_prefix_tf
        self.out_units = out_units
        if out_units is not None:
            self.output_linear = nn.Linear(output_size, out_units)

    def output_size(self) -> int:
        return self._output_size

    def forward(
        self,
        xs_pad: torch.Tensor,
        ilens: torch.Tensor,
        prev_states: torch.Tensor = None,
        ctc: CTC = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, Optional[torch.Tensor]]:
        """Embed positions in tensor.

        Args:
            xs_pad: input tensor (B, L, D)
            ilens: input length (B)
            prev_states: Not to be used now.
        Returns:
            position embedded tensor and mask
        """
        masks = (~make_pad_mask(ilens)[:, None, :]).to(xs_pad.device)
        xs_pad = xs_pad * self.output_size() ** 0.5
        if self.embed is None:
            xs_pad = xs_pad
        elif (
            isinstance(self.embed, Conv2dSubsampling)
            or isinstance(self.embed, Conv2dSubsampling2)
            or isinstance(self.embed, Conv2dSubsampling6)
            or isinstance(self.embed, Conv2dSubsampling8)
        ):
            short_status, limit_size = check_short_utt(self.embed, xs_pad.size(1))
            if short_status:
                raise TooShortUttError(
                    f"has {xs_pad.size(1)} frames and is too short for subsampling "
                    + f"(it needs more than {limit_size} frames), return empty results",
                    xs_pad.size(1),
                    limit_size,
                )
            xs_pad, masks = self.embed(xs_pad, masks)
        else:
            xs_pad = self.embed(xs_pad)

        xs_pad = self.dropout(xs_pad)
        # encoder_outs = self.encoders0(xs_pad, masks)
        # xs_pad, masks = encoder_outs[0], encoder_outs[1]
        intermediate_outs = []
        if len(self.interctc_layer_idx) == 0:
            encoder_outs = self.encoders(xs_pad, masks)
            xs_pad, masks = encoder_outs[0], encoder_outs[1]
        else:
            for layer_idx, encoder_layer in enumerate(self.encoders):
                encoder_outs = encoder_layer(xs_pad, masks)
                xs_pad, masks = encoder_outs[0], encoder_outs[1]

                if layer_idx + 1 in self.interctc_layer_idx:
                    encoder_out = xs_pad

                    # intermediate outputs are also normalized
                    if self.normalize_before:
                        encoder_out = self.after_norm(encoder_out)

                    intermediate_outs.append((layer_idx + 1, encoder_out))

                    if self.interctc_use_conditioning:
                        ctc_out = ctc.softmax(encoder_out)
                        xs_pad = xs_pad + self.conditioning_layer(ctc_out)

        if self.normalize_before:
            xs_pad = self.after_norm(xs_pad)

        if self.out_units is not None:
            xs_pad = self.output_linear(xs_pad)
        olens = masks.squeeze(1).sum(1)
        if len(intermediate_outs) > 0:
            return (xs_pad, intermediate_outs), olens, None
        return xs_pad, olens, None

    def gen_tf2torch_map_dict(self):
        tensor_name_prefix_torch = self.tf2torch_tensor_name_prefix_torch
        tensor_name_prefix_tf = self.tf2torch_tensor_name_prefix_tf
        map_dict_local = {
            # cicd
            # torch: conv1d.weight in "out_channel in_channel kernel_size"
            # tf   : conv1d.weight in "kernel_size in_channel out_channel"
            # torch: linear.weight in "out_channel in_channel"
            # tf   :  dense.weight in "in_channel out_channel"
            "{}.encoders.layeridx.norm1.weight".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/multi_head/LayerNorm/gamma".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },  # (256,),(256,)
            "{}.encoders.layeridx.norm1.bias".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/multi_head/LayerNorm/beta".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },  # (256,),(256,)
            "{}.encoders.layeridx.self_attn.linear_q_k_v.weight".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/multi_head/conv1d/kernel".format(tensor_name_prefix_tf),
                "squeeze": 0,
                "transpose": (1, 0),
            },  # (768,256),(1,256,768)
            "{}.encoders.layeridx.self_attn.linear_q_k_v.bias".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/multi_head/conv1d/bias".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },  # (768,),(768,)
            "{}.encoders.layeridx.self_attn.linear_out.weight".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/multi_head/conv1d_1/kernel".format(tensor_name_prefix_tf),
                "squeeze": 0,
                "transpose": (1, 0),
            },  # (256,256),(1,256,256)
            "{}.encoders.layeridx.self_attn.linear_out.bias".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/multi_head/conv1d_1/bias".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },  # (256,),(256,)
            # ffn
            "{}.encoders.layeridx.norm2.weight".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/ffn/LayerNorm/gamma".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },  # (256,),(256,)
            "{}.encoders.layeridx.norm2.bias".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/ffn/LayerNorm/beta".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },  # (256,),(256,)
            "{}.encoders.layeridx.feed_forward.w_1.weight".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/ffn/conv1d/kernel".format(tensor_name_prefix_tf),
                "squeeze": 0,
                "transpose": (1, 0),
            },  # (1024,256),(1,256,1024)
            "{}.encoders.layeridx.feed_forward.w_1.bias".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/ffn/conv1d/bias".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },  # (1024,),(1024,)
            "{}.encoders.layeridx.feed_forward.w_2.weight".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/ffn/conv1d_1/kernel".format(tensor_name_prefix_tf),
                "squeeze": 0,
                "transpose": (1, 0),
            },  # (256,1024),(1,1024,256)
            "{}.encoders.layeridx.feed_forward.w_2.bias".format(tensor_name_prefix_torch): {
                "name": "{}/layer_layeridx/ffn/conv1d_1/bias".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },  # (256,),(256,)
            # out norm
            "{}.after_norm.weight".format(tensor_name_prefix_torch): {
                "name": "{}/LayerNorm/gamma".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },  # (256,),(256,)
            "{}.after_norm.bias".format(tensor_name_prefix_torch): {
                "name": "{}/LayerNorm/beta".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },  # (256,),(256,)
        }
        if self.out_units is not None:
            map_dict_local.update({
                "{}.output_linear.weight".format(tensor_name_prefix_torch): {
                    "name": "{}/conv1d/kernel".format(tensor_name_prefix_tf),
                    "squeeze": 0,
                    "transpose": (1, 0),
                },
                "{}.output_linear.bias".format(tensor_name_prefix_torch): {
                    "name": "{}/conv1d/bias".format(tensor_name_prefix_tf),
                    "squeeze": None,
                    "transpose": None,
                },  # (256,),(256,)
            })

        return map_dict_local

    def convert_tf2torch(
        self,
        var_dict_tf,
        var_dict_torch,
    ):

        map_dict = self.gen_tf2torch_map_dict()

        var_dict_torch_update = dict()
        for name in sorted(var_dict_torch.keys(), reverse=False):
            if name.startswith(self.tf2torch_tensor_name_prefix_torch):
                # process special (first and last) layers
                if name in map_dict:
                    name_tf = map_dict[name]["name"]
                    data_tf = var_dict_tf[name_tf]
                    data_tf = torch.from_numpy(data_tf).type(torch.float32).to("cpu")
                    if map_dict[name]["squeeze"] is not None:
                        data_tf = np.squeeze(data_tf, axis=map_dict[name]["squeeze"])
                    if map_dict[name]["transpose"] is not None:
                        data_tf = np.transpose(data_tf, map_dict[name]["transpose"])
                    assert var_dict_torch[name].size() == data_tf.size(), "{}, {}, {} != {}".format(
                        name, name_tf, var_dict_torch[name].size(), data_tf.size()
                    )
                    var_dict_torch_update[name] = data_tf
                    logging.info(
                        "torch tensor: {}, {}, loading from tf tensor: {}, {}".format(
                            name, data_tf.size(), name_tf, var_dict_tf[name_tf].shape
                        )
                    )
                # process general layers
                else:
                    # self.tf2torch_tensor_name_prefix_torch may include ".", solve this case
                    names = name.replace(self.tf2torch_tensor_name_prefix_torch, "todo").split(".")
                    layeridx = int(names[2])
                    name_q = name.replace(".{}.".format(layeridx), ".layeridx.")
                    if name_q in map_dict.keys():
                        name_v = map_dict[name_q]["name"]
                        name_tf = name_v.replace("layeridx", "{}".format(layeridx))
                        data_tf = var_dict_tf[name_tf]
                        if map_dict[name_q]["squeeze"] is not None:
                            data_tf = np.squeeze(data_tf, axis=map_dict[name_q]["squeeze"])
                        if map_dict[name_q]["transpose"] is not None:
                            data_tf = np.transpose(data_tf, map_dict[name_q]["transpose"])
                        data_tf = torch.from_numpy(data_tf).type(torch.float32).to("cpu")
                        assert var_dict_torch[name].size() == data_tf.size(), "{}, {}, {} != {}".format(
                            name, name_tf, var_dict_torch[name].size(), data_tf.size()
                        )
                        var_dict_torch_update[name] = data_tf
                        logging.info(
                            "torch tensor: {}, {}, loading from tf tensor: {}, {}".format(
                                name,
                                data_tf.size(),
                                name_tf,
                                var_dict_tf[name_tf].shape,
                            )
                        )
                    else:
                        logging.warning("{} is missed from tf checkpoint".format(name))

        return var_dict_torch_update
