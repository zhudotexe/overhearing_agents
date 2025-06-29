import logging
from collections import OrderedDict
from typing import Optional, Tuple

import numpy as np
import torch
from funasr_detach.models.encoder.abs_encoder import AbsEncoder
from funasr_detach.models.pooling.statistic_pooling import (
    statistic_pooling,
    windowed_statistic_pooling,
)
from torch.nn import functional as F


class BasicLayer(torch.nn.Module):

    def __init__(self, in_filters: int, filters: int, stride: int, bn_momentum: float = 0.5):

        super().__init__()
        self.stride = stride
        self.in_filters = in_filters
        self.filters = filters

        self.bn1 = torch.nn.BatchNorm2d(in_filters, eps=1e-3, momentum=bn_momentum, affine=True)
        self.relu1 = torch.nn.ReLU()
        self.conv1 = torch.nn.Conv2d(in_filters, filters, 3, stride, bias=False)

        self.bn2 = torch.nn.BatchNorm2d(filters, eps=1e-3, momentum=bn_momentum, affine=True)
        self.relu2 = torch.nn.ReLU()
        self.conv2 = torch.nn.Conv2d(filters, filters, 3, 1, bias=False)

        if in_filters != filters or stride > 1:
            self.conv_sc = torch.nn.Conv2d(in_filters, filters, 1, stride, bias=False)
            self.bn_sc = torch.nn.BatchNorm2d(filters, eps=1e-3, momentum=bn_momentum, affine=True)

    def proper_padding(self, x, stride):
        # align padding mode to tf.layers.conv2d with padding_mod="same"
        if stride == 1:
            return F.pad(x, (1, 1, 1, 1), "constant", 0)
        elif stride == 2:
            h, w = x.size(2), x.size(3)
            # (left, right, top, bottom)
            return F.pad(x, (w % 2, 1, h % 2, 1), "constant", 0)

    def forward(self, xs_pad, ilens):
        identity = xs_pad
        if self.in_filters != self.filters or self.stride > 1:
            identity = self.conv_sc(identity)
            identity = self.bn_sc(identity)

        xs_pad = self.relu1(self.bn1(xs_pad))
        xs_pad = self.proper_padding(xs_pad, self.stride)
        xs_pad = self.conv1(xs_pad)

        xs_pad = self.relu2(self.bn2(xs_pad))
        xs_pad = self.proper_padding(xs_pad, 1)
        xs_pad = self.conv2(xs_pad)

        if self.stride == 2:
            ilens = (ilens + 1) // self.stride

        return xs_pad + identity, ilens


class BasicBlock(torch.nn.Module):
    def __init__(self, in_filters, filters, num_layer, stride, bn_momentum=0.5):
        super().__init__()
        self.num_layer = num_layer

        for i in range(num_layer):
            layer = BasicLayer(
                in_filters if i == 0 else filters,
                filters,
                stride if i == 0 else 1,
                bn_momentum,
            )
            self.add_module("layer_{}".format(i), layer)

    def forward(self, xs_pad, ilens):

        for i in range(self.num_layer):
            xs_pad, ilens = self._modules["layer_{}".format(i)](xs_pad, ilens)

        return xs_pad, ilens


class ResNet34(AbsEncoder):
    def __init__(
        self,
        input_size,
        use_head_conv=True,
        batchnorm_momentum=0.5,
        use_head_maxpool=False,
        num_nodes_pooling_layer=256,
        layers_in_block=(3, 4, 6, 3),
        filters_in_block=(32, 64, 128, 256),
    ):
        super(ResNet34, self).__init__()

        self.use_head_conv = use_head_conv
        self.use_head_maxpool = use_head_maxpool
        self.num_nodes_pooling_layer = num_nodes_pooling_layer
        self.layers_in_block = layers_in_block
        self.filters_in_block = filters_in_block
        self.input_size = input_size

        pre_filters = filters_in_block[0]
        if use_head_conv:
            self.pre_conv = torch.nn.Conv2d(1, pre_filters, 3, 1, 1, bias=False, padding_mode="zeros")
            self.pre_conv_bn = torch.nn.BatchNorm2d(pre_filters, eps=1e-3, momentum=batchnorm_momentum)

        if use_head_maxpool:
            self.head_maxpool = torch.nn.MaxPool2d(3, 1, padding=1)

        for i in range(len(layers_in_block)):
            if i == 0:
                in_filters = pre_filters if self.use_head_conv else 1
            else:
                in_filters = filters_in_block[i - 1]

            block = BasicBlock(
                in_filters,
                filters=filters_in_block[i],
                num_layer=layers_in_block[i],
                stride=1 if i == 0 else 2,
                bn_momentum=batchnorm_momentum,
            )
            self.add_module("block_{}".format(i), block)

        self.resnet0_dense = torch.nn.Conv2d(filters_in_block[-1], num_nodes_pooling_layer, 1)
        self.resnet0_bn = torch.nn.BatchNorm2d(num_nodes_pooling_layer, eps=1e-3, momentum=batchnorm_momentum)

        self.time_ds_ratio = 8

    def output_size(self) -> int:
        return self.num_nodes_pooling_layer

    def forward(
        self,
        xs_pad: torch.Tensor,
        ilens: torch.Tensor,
        prev_states: torch.Tensor = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:

        features = xs_pad
        assert features.size(-1) == self.input_size, "Dimension of features {} doesn't match the input_size {}.".format(
            features.size(-1), self.input_size
        )
        features = torch.unsqueeze(features, dim=1)
        if self.use_head_conv:
            features = self.pre_conv(features)
            features = self.pre_conv_bn(features)
            features = F.relu(features)

        if self.use_head_maxpool:
            features = self.head_maxpool(features)

        resnet_outs, resnet_out_lens = features, ilens
        for i in range(len(self.layers_in_block)):
            block = self._modules["block_{}".format(i)]
            resnet_outs, resnet_out_lens = block(resnet_outs, resnet_out_lens)

        features = self.resnet0_dense(resnet_outs)
        features = F.relu(features)
        features = self.resnet0_bn(features)

        return features, resnet_out_lens


# Note: For training, this implement is not equivalent to tf because of the kernel_regularizer in tf.layers.
# TODO: implement kernel_regularizer in torch with munal loss addition or weigth_decay in the optimizer
class ResNet34_SP_L2Reg(AbsEncoder):
    def __init__(
        self,
        input_size,
        use_head_conv=True,
        batchnorm_momentum=0.5,
        use_head_maxpool=False,
        num_nodes_pooling_layer=256,
        layers_in_block=(3, 4, 6, 3),
        filters_in_block=(32, 64, 128, 256),
        tf2torch_tensor_name_prefix_torch="encoder",
        tf2torch_tensor_name_prefix_tf="EAND/speech_encoder",
        tf_train_steps=720000,
    ):
        super(ResNet34_SP_L2Reg, self).__init__()

        self.use_head_conv = use_head_conv
        self.use_head_maxpool = use_head_maxpool
        self.num_nodes_pooling_layer = num_nodes_pooling_layer
        self.layers_in_block = layers_in_block
        self.filters_in_block = filters_in_block
        self.input_size = input_size
        self.tf2torch_tensor_name_prefix_torch = tf2torch_tensor_name_prefix_torch
        self.tf2torch_tensor_name_prefix_tf = tf2torch_tensor_name_prefix_tf
        self.tf_train_steps = tf_train_steps

        pre_filters = filters_in_block[0]
        if use_head_conv:
            self.pre_conv = torch.nn.Conv2d(1, pre_filters, 3, 1, 1, bias=False, padding_mode="zeros")
            self.pre_conv_bn = torch.nn.BatchNorm2d(pre_filters, eps=1e-3, momentum=batchnorm_momentum)

        if use_head_maxpool:
            self.head_maxpool = torch.nn.MaxPool2d(3, 1, padding=1)

        for i in range(len(layers_in_block)):
            if i == 0:
                in_filters = pre_filters if self.use_head_conv else 1
            else:
                in_filters = filters_in_block[i - 1]

            block = BasicBlock(
                in_filters,
                filters=filters_in_block[i],
                num_layer=layers_in_block[i],
                stride=1 if i == 0 else 2,
                bn_momentum=batchnorm_momentum,
            )
            self.add_module("block_{}".format(i), block)

        self.resnet0_dense = torch.nn.Conv1d(filters_in_block[-1] * input_size // 8, num_nodes_pooling_layer, 1)
        self.resnet0_bn = torch.nn.BatchNorm1d(num_nodes_pooling_layer, eps=1e-3, momentum=batchnorm_momentum)

        self.time_ds_ratio = 8

    def output_size(self) -> int:
        return self.num_nodes_pooling_layer

    def forward(
        self,
        xs_pad: torch.Tensor,
        ilens: torch.Tensor,
        prev_states: torch.Tensor = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:

        features = xs_pad
        assert features.size(-1) == self.input_size, "Dimension of features {} doesn't match the input_size {}.".format(
            features.size(-1), self.input_size
        )
        features = torch.unsqueeze(features, dim=1)
        if self.use_head_conv:
            features = self.pre_conv(features)
            features = self.pre_conv_bn(features)
            features = F.relu(features)

        if self.use_head_maxpool:
            features = self.head_maxpool(features)

        resnet_outs, resnet_out_lens = features, ilens
        for i in range(len(self.layers_in_block)):
            block = self._modules["block_{}".format(i)]
            resnet_outs, resnet_out_lens = block(resnet_outs, resnet_out_lens)

        # B, C, T, F
        bb, cc, tt, ff = resnet_outs.shape
        resnet_outs = torch.reshape(resnet_outs.permute(0, 3, 1, 2), [bb, ff * cc, tt])
        features = self.resnet0_dense(resnet_outs)
        features = F.relu(features)
        features = self.resnet0_bn(features)

        return features, resnet_out_lens

    def gen_tf2torch_map_dict(self):
        tensor_name_prefix_torch = self.tf2torch_tensor_name_prefix_torch
        tensor_name_prefix_tf = self.tf2torch_tensor_name_prefix_tf
        train_steps = self.tf_train_steps
        map_dict_local = {
            # torch: conv1d.weight in "out_channel in_channel kernel_size"
            # tf   : conv1d.weight in "kernel_size in_channel out_channel"
            # torch: linear.weight in "out_channel in_channel"
            # tf   :  dense.weight in "in_channel out_channel"
            "{}.pre_conv.weight".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv/kernel".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": (3, 2, 0, 1),
            },
            "{}.pre_conv_bn.bias".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/beta".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.weight".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/gamma".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.running_mean".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/moving_mean".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.running_var".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/moving_variance".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.num_batches_tracked".format(tensor_name_prefix_torch): train_steps,
        }
        for layer_idx in range(3):
            map_dict_local.update({
                "{}.resnet{}_dense.weight".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_dense/kernel".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": (2, 1, 0) if layer_idx == 0 else (1, 0),
                },
                "{}.resnet{}_dense.bias".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_dense/bias".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.weight".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/gamma".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.bias".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/beta".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.running_mean".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/moving_mean".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.running_var".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/moving_variance".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.num_batches_tracked".format(tensor_name_prefix_torch, layer_idx): train_steps,
            })

        for block_idx in range(len(self.layers_in_block)):
            for layer_idx in range(self.layers_in_block[block_idx]):
                for i in ["1", "2", "_sc"]:
                    map_dict_local.update({
                        "{}.block_{}.layer_{}.conv{}.weight".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): {
                            "name": "{}/block_{}/layer_{}/conv{}/kernel".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": (3, 2, 0, 1),
                        },
                        "{}.block_{}.layer_{}.bn{}.weight".format(tensor_name_prefix_torch, block_idx, layer_idx, i): {
                            "name": "{}/block_{}/layer_{}/bn{}/gamma".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.bias".format(tensor_name_prefix_torch, block_idx, layer_idx, i): {
                            "name": "{}/block_{}/layer_{}/bn{}/beta".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.running_mean".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): {
                            "name": "{}/block_{}/layer_{}/bn{}/moving_mean".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.running_var".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): {
                            "name": "{}/block_{}/layer_{}/bn{}/moving_variance".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.num_batches_tracked".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): train_steps,
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
                if name in map_dict:
                    if "num_batches_tracked" not in name:
                        name_tf = map_dict[name]["name"]
                        data_tf = var_dict_tf[name_tf]
                        if map_dict[name]["squeeze"] is not None:
                            data_tf = np.squeeze(data_tf, axis=map_dict[name]["squeeze"])
                        if map_dict[name]["transpose"] is not None:
                            data_tf = np.transpose(data_tf, map_dict[name]["transpose"])
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
                        var_dict_torch_update[name] = torch.Tensor(map_dict[name]).type(torch.int64).to("cpu")
                        logging.info("torch tensor: {}, manually assigning to: {}".format(name, map_dict[name]))
                else:
                    logging.warning("{} is missed from tf checkpoint".format(name))

        return var_dict_torch_update


class ResNet34Diar(ResNet34):
    def __init__(
        self,
        input_size,
        embedding_node="resnet1_dense",
        use_head_conv=True,
        batchnorm_momentum=0.5,
        use_head_maxpool=False,
        num_nodes_pooling_layer=256,
        layers_in_block=(3, 4, 6, 3),
        filters_in_block=(32, 64, 128, 256),
        num_nodes_resnet1=256,
        num_nodes_last_layer=256,
        pooling_type="window_shift",
        pool_size=20,
        stride=1,
        tf2torch_tensor_name_prefix_torch="encoder",
        tf2torch_tensor_name_prefix_tf="seq2seq/speech_encoder",
    ):
        """
        Author: Speech Lab, Alibaba Group, China
        SOND: Speaker Overlap-aware Neural Diarization for Multi-party Meeting Analysis
        https://arxiv.org/abs/2211.10243
        """

        super(ResNet34Diar, self).__init__(
            input_size,
            use_head_conv=use_head_conv,
            batchnorm_momentum=batchnorm_momentum,
            use_head_maxpool=use_head_maxpool,
            num_nodes_pooling_layer=num_nodes_pooling_layer,
            layers_in_block=layers_in_block,
            filters_in_block=filters_in_block,
        )

        self.embedding_node = embedding_node
        self.num_nodes_resnet1 = num_nodes_resnet1
        self.num_nodes_last_layer = num_nodes_last_layer
        self.pooling_type = pooling_type
        self.pool_size = pool_size
        self.stride = stride
        self.tf2torch_tensor_name_prefix_torch = tf2torch_tensor_name_prefix_torch
        self.tf2torch_tensor_name_prefix_tf = tf2torch_tensor_name_prefix_tf

        self.resnet1_dense = torch.nn.Linear(num_nodes_pooling_layer * 2, num_nodes_resnet1)
        self.resnet1_bn = torch.nn.BatchNorm1d(num_nodes_resnet1, eps=1e-3, momentum=batchnorm_momentum)

        self.resnet2_dense = torch.nn.Linear(num_nodes_resnet1, num_nodes_last_layer)
        self.resnet2_bn = torch.nn.BatchNorm1d(num_nodes_last_layer, eps=1e-3, momentum=batchnorm_momentum)

    def output_size(self) -> int:
        if self.embedding_node.startswith("resnet1"):
            return self.num_nodes_resnet1
        elif self.embedding_node.startswith("resnet2"):
            return self.num_nodes_last_layer

        return self.num_nodes_pooling_layer

    def forward(
        self,
        xs_pad: torch.Tensor,
        ilens: torch.Tensor,
        prev_states: torch.Tensor = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, Optional[torch.Tensor]]:

        endpoints = OrderedDict()
        res_out, ilens = super().forward(xs_pad, ilens)
        endpoints["resnet0_bn"] = res_out
        if self.pooling_type == "frame_gsp":
            features = statistic_pooling(res_out, ilens, (3,))
        else:
            features, ilens = windowed_statistic_pooling(res_out, ilens, (2, 3), self.pool_size, self.stride)
        features = features.transpose(1, 2)
        endpoints["pooling"] = features

        features = self.resnet1_dense(features)
        endpoints["resnet1_dense"] = features
        features = F.relu(features)
        endpoints["resnet1_relu"] = features
        features = self.resnet1_bn(features.transpose(1, 2)).transpose(1, 2)
        endpoints["resnet1_bn"] = features

        features = self.resnet2_dense(features)
        endpoints["resnet2_dense"] = features
        features = F.relu(features)
        endpoints["resnet2_relu"] = features
        features = self.resnet2_bn(features.transpose(1, 2)).transpose(1, 2)
        endpoints["resnet2_bn"] = features

        return endpoints[self.embedding_node], ilens, None

    def gen_tf2torch_map_dict(self):
        tensor_name_prefix_torch = self.tf2torch_tensor_name_prefix_torch
        tensor_name_prefix_tf = self.tf2torch_tensor_name_prefix_tf
        train_steps = 300000
        map_dict_local = {
            # torch: conv1d.weight in "out_channel in_channel kernel_size"
            # tf   : conv1d.weight in "kernel_size in_channel out_channel"
            # torch: linear.weight in "out_channel in_channel"
            # tf   :  dense.weight in "in_channel out_channel"
            "{}.pre_conv.weight".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv/kernel".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": (3, 2, 0, 1),
            },
            "{}.pre_conv_bn.bias".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/beta".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.weight".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/gamma".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.running_mean".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/moving_mean".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.running_var".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/moving_variance".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.num_batches_tracked".format(tensor_name_prefix_torch): train_steps,
        }
        for layer_idx in range(3):
            map_dict_local.update({
                "{}.resnet{}_dense.weight".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_dense/kernel".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": (3, 2, 0, 1) if layer_idx == 0 else (1, 0),
                },
                "{}.resnet{}_dense.bias".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_dense/bias".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.weight".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/gamma".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.bias".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/beta".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.running_mean".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/moving_mean".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.running_var".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/moving_variance".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.num_batches_tracked".format(tensor_name_prefix_torch, layer_idx): train_steps,
            })

        for block_idx in range(len(self.layers_in_block)):
            for layer_idx in range(self.layers_in_block[block_idx]):
                for i in ["1", "2", "_sc"]:
                    map_dict_local.update({
                        "{}.block_{}.layer_{}.conv{}.weight".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): {
                            "name": "{}/block_{}/layer_{}/conv{}/kernel".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": (3, 2, 0, 1),
                        },
                        "{}.block_{}.layer_{}.bn{}.weight".format(tensor_name_prefix_torch, block_idx, layer_idx, i): {
                            "name": "{}/block_{}/layer_{}/bn{}/gamma".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.bias".format(tensor_name_prefix_torch, block_idx, layer_idx, i): {
                            "name": "{}/block_{}/layer_{}/bn{}/beta".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.running_mean".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): {
                            "name": "{}/block_{}/layer_{}/bn{}/moving_mean".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.running_var".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): {
                            "name": "{}/block_{}/layer_{}/bn{}/moving_variance".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.num_batches_tracked".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): train_steps,
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
                if name in map_dict:
                    if "num_batches_tracked" not in name:
                        name_tf = map_dict[name]["name"]
                        data_tf = var_dict_tf[name_tf]
                        if map_dict[name]["squeeze"] is not None:
                            data_tf = np.squeeze(data_tf, axis=map_dict[name]["squeeze"])
                        if map_dict[name]["transpose"] is not None:
                            data_tf = np.transpose(data_tf, map_dict[name]["transpose"])
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
                        var_dict_torch_update[name] = torch.Tensor(map_dict[name]).type(torch.int64).to("cpu")
                        logging.info("torch tensor: {}, manually assigning to: {}".format(name, map_dict[name]))
                else:
                    logging.warning("{} is missed from tf checkpoint".format(name))

        return var_dict_torch_update


class ResNet34SpL2RegDiar(ResNet34_SP_L2Reg):
    def __init__(
        self,
        input_size,
        embedding_node="resnet1_dense",
        use_head_conv=True,
        batchnorm_momentum=0.5,
        use_head_maxpool=False,
        num_nodes_pooling_layer=256,
        layers_in_block=(3, 4, 6, 3),
        filters_in_block=(32, 64, 128, 256),
        num_nodes_resnet1=256,
        num_nodes_last_layer=256,
        pooling_type="window_shift",
        pool_size=20,
        stride=1,
        tf2torch_tensor_name_prefix_torch="encoder",
        tf2torch_tensor_name_prefix_tf="seq2seq/speech_encoder",
    ):
        """
        Author: Speech Lab, Alibaba Group, China
        TOLD: A Novel Two-Stage Overlap-Aware Framework for Speaker Diarization
        https://arxiv.org/abs/2303.05397
        """

        super(ResNet34SpL2RegDiar, self).__init__(
            input_size,
            use_head_conv=use_head_conv,
            batchnorm_momentum=batchnorm_momentum,
            use_head_maxpool=use_head_maxpool,
            num_nodes_pooling_layer=num_nodes_pooling_layer,
            layers_in_block=layers_in_block,
            filters_in_block=filters_in_block,
        )

        self.embedding_node = embedding_node
        self.num_nodes_resnet1 = num_nodes_resnet1
        self.num_nodes_last_layer = num_nodes_last_layer
        self.pooling_type = pooling_type
        self.pool_size = pool_size
        self.stride = stride
        self.tf2torch_tensor_name_prefix_torch = tf2torch_tensor_name_prefix_torch
        self.tf2torch_tensor_name_prefix_tf = tf2torch_tensor_name_prefix_tf

        self.resnet1_dense = torch.nn.Linear(num_nodes_pooling_layer * 2, num_nodes_resnet1)
        self.resnet1_bn = torch.nn.BatchNorm1d(num_nodes_resnet1, eps=1e-3, momentum=batchnorm_momentum)

        self.resnet2_dense = torch.nn.Linear(num_nodes_resnet1, num_nodes_last_layer)
        self.resnet2_bn = torch.nn.BatchNorm1d(num_nodes_last_layer, eps=1e-3, momentum=batchnorm_momentum)

    def output_size(self) -> int:
        if self.embedding_node.startswith("resnet1"):
            return self.num_nodes_resnet1
        elif self.embedding_node.startswith("resnet2"):
            return self.num_nodes_last_layer

        return self.num_nodes_pooling_layer

    def forward(
        self,
        xs_pad: torch.Tensor,
        ilens: torch.Tensor,
        prev_states: torch.Tensor = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, Optional[torch.Tensor]]:

        endpoints = OrderedDict()
        res_out, ilens = super().forward(xs_pad, ilens)
        endpoints["resnet0_bn"] = res_out
        if self.pooling_type == "frame_gsp":
            features = statistic_pooling(res_out, ilens, (2,))
        else:
            features, ilens = windowed_statistic_pooling(res_out, ilens, (2,), self.pool_size, self.stride)
        features = features.transpose(1, 2)
        endpoints["pooling"] = features

        features = self.resnet1_dense(features)
        endpoints["resnet1_dense"] = features
        features = F.relu(features)
        endpoints["resnet1_relu"] = features
        features = self.resnet1_bn(features.transpose(1, 2)).transpose(1, 2)
        endpoints["resnet1_bn"] = features

        features = self.resnet2_dense(features)
        endpoints["resnet2_dense"] = features
        features = F.relu(features)
        endpoints["resnet2_relu"] = features
        features = self.resnet2_bn(features.transpose(1, 2)).transpose(1, 2)
        endpoints["resnet2_bn"] = features

        return endpoints[self.embedding_node], ilens, None

    def gen_tf2torch_map_dict(self):
        tensor_name_prefix_torch = self.tf2torch_tensor_name_prefix_torch
        tensor_name_prefix_tf = self.tf2torch_tensor_name_prefix_tf
        train_steps = 720000
        map_dict_local = {
            # torch: conv1d.weight in "out_channel in_channel kernel_size"
            # tf   : conv1d.weight in "kernel_size in_channel out_channel"
            # torch: linear.weight in "out_channel in_channel"
            # tf   :  dense.weight in "in_channel out_channel"
            "{}.pre_conv.weight".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv/kernel".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": (3, 2, 0, 1),
            },
            "{}.pre_conv_bn.bias".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/beta".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.weight".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/gamma".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.running_mean".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/moving_mean".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.running_var".format(tensor_name_prefix_torch): {
                "name": "{}/pre_conv_bn/moving_variance".format(tensor_name_prefix_tf),
                "squeeze": None,
                "transpose": None,
            },
            "{}.pre_conv_bn.num_batches_tracked".format(tensor_name_prefix_torch): train_steps,
        }
        for layer_idx in range(3):
            map_dict_local.update({
                "{}.resnet{}_dense.weight".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_dense/kernel".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": (2, 1, 0) if layer_idx == 0 else (1, 0),
                },
                "{}.resnet{}_dense.bias".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_dense/bias".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.weight".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/gamma".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.bias".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/beta".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.running_mean".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/moving_mean".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.running_var".format(tensor_name_prefix_torch, layer_idx): {
                    "name": "{}/resnet{}_bn/moving_variance".format(tensor_name_prefix_tf, layer_idx),
                    "squeeze": None,
                    "transpose": None,
                },
                "{}.resnet{}_bn.num_batches_tracked".format(tensor_name_prefix_torch, layer_idx): train_steps,
            })

        for block_idx in range(len(self.layers_in_block)):
            for layer_idx in range(self.layers_in_block[block_idx]):
                for i in ["1", "2", "_sc"]:
                    map_dict_local.update({
                        "{}.block_{}.layer_{}.conv{}.weight".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): {
                            "name": "{}/block_{}/layer_{}/conv{}/kernel".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": (3, 2, 0, 1),
                        },
                        "{}.block_{}.layer_{}.bn{}.weight".format(tensor_name_prefix_torch, block_idx, layer_idx, i): {
                            "name": "{}/block_{}/layer_{}/bn{}/gamma".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.bias".format(tensor_name_prefix_torch, block_idx, layer_idx, i): {
                            "name": "{}/block_{}/layer_{}/bn{}/beta".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.running_mean".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): {
                            "name": "{}/block_{}/layer_{}/bn{}/moving_mean".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.running_var".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): {
                            "name": "{}/block_{}/layer_{}/bn{}/moving_variance".format(
                                tensor_name_prefix_tf, block_idx, layer_idx, i
                            ),
                            "squeeze": None,
                            "transpose": None,
                        },
                        "{}.block_{}.layer_{}.bn{}.num_batches_tracked".format(
                            tensor_name_prefix_torch, block_idx, layer_idx, i
                        ): train_steps,
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
                if name in map_dict:
                    if "num_batches_tracked" not in name:
                        name_tf = map_dict[name]["name"]
                        data_tf = var_dict_tf[name_tf]
                        if map_dict[name]["squeeze"] is not None:
                            data_tf = np.squeeze(data_tf, axis=map_dict[name]["squeeze"])
                        if map_dict[name]["transpose"] is not None:
                            data_tf = np.transpose(data_tf, map_dict[name]["transpose"])
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
                        var_dict_torch_update[name] = (
                            torch.from_numpy(np.array(map_dict[name])).type(torch.int64).to("cpu")
                        )
                        logging.info("torch tensor: {}, manually assigning to: {}".format(name, map_dict[name]))
                else:
                    logging.warning("{} is missed from tf checkpoint".format(name))

        return var_dict_torch_update
