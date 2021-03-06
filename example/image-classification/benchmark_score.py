# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Benchmark the scoring performance on various CNNs
"""
from common import find_mxnet
from common.util import get_gpus
import mxnet as mx
from importlib import import_module
import logging
import time
import numpy as np
logging.basicConfig(level=logging.DEBUG)

def get_symbol(network, batch_size, dtype):
    image_shape = (3,299,299) if network == 'inception-v3' else (3,224,224)
    num_layers = 0
    if 'resnet' in network:
        num_layers = int(network.split('-')[1])
        network = 'resnet'
    if 'vgg' in network:
        num_layers = int(network.split('-')[1])
        network = 'vgg'
    net = import_module('symbols.'+network)
    sym = net.get_symbol(num_classes=1000,
                         image_shape=','.join([str(i) for i in image_shape]),
                         num_layers=num_layers,
                         dtype=dtype)
    return (sym, [('data', (batch_size,)+image_shape)])

def score(network, dev, batch_size, num_batches, dtype):
    # get mod
    sym, data_shape = get_symbol(network, batch_size, dtype)
    mod = mx.mod.Module(symbol=sym, context=dev)
    mod.bind(for_training     = False,
             inputs_need_grad = False,
             data_shapes      = data_shape)
    mod.init_params(initializer=mx.init.Xavier(magnitude=2.))

    # get data
    data = [mx.random.uniform(-1.0, 1.0, shape=shape, ctx=dev) for _, shape in mod.data_shapes]
    batch = mx.io.DataBatch(data, []) # empty label

    # run
    dry_run = 5                 # use 5 iterations to warm up
    for i in range(dry_run+num_batches):
        if i == dry_run:
            tic = time.time()
        mod.forward(batch, is_train=False)
        for output in mod.get_outputs():
            output.wait_to_read()

    # return num images per second
    return num_batches*batch_size/(time.time() - tic)

if __name__ == '__main__':
    networks = ['alexnet', 'vgg-16', 'inception-bn', 'inception-v3', 'resnet-50', 'resnet-152']
    devs = [mx.gpu(0)] if len(get_gpus()) > 0 else []
    # Enable USE_MKLDNN for better CPU performance
    devs.append(mx.cpu())

    batch_sizes = [1, 2, 4, 8, 16, 32]
    for net in networks:
        logging.info('network: %s', net)
        for d in devs:
            logging.info('device: %s', d)
            for b in batch_sizes:
                for dtype in ['float32', 'float16']:
                    if d == mx.cpu() and dtype == 'float16':
                        #float16 is not supported on CPU
                        continue
                    elif net in ['inception-bn', 'alexnet'] and dt == 'float16':
                        logging.info('{} does not support float16'.format(net))
                    else:
                        speed = score(network=net, dev=d, batch_size=b, num_batches=10, dtype=dtype)
                        logging.info('batch size %2d, dtype %s image/sec: %f', b, dtype, speed)
