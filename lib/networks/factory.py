# --------------------------------------------------------
# SubCNN_TF
# Copyright (c) 2016 CVGL Stanford
# Licensed under The MIT License [see LICENSE for details]
# Written by Yu Xiang
# --------------------------------------------------------

"""Factory method for easily getting imdbs by name."""

__sets = {}

import networks.VGGnet_train
import networks.VGGnet_test
import pdb
import tensorflow as tf

#__sets['VGGnet_train'] = networks.VGGnet_train()

#__sets['VGGnet_test'] = networks.VGGnet_test()

def get_network(name):
    """Get a network by name."""
    nwnm = name.split('_')[1]
    #if not __sets.has_key(name):
    #    raise KeyError('Unknown dataset: {}'.format(name))
    #return __sets[name]
    if (nwnm in ['train07', 'train09']):
        # we have to re-train low-level ConvNet from scratch
        return networks.VGGnet_train(low_level_trainable=True)
    elif (nwnm in ['test07', 'test09']):
        # we have to re-train low-level ConvNet from scratch
        return networks.VGGnet_test(low_level_trainable=True)
    elif (nwnm in ['train08', 'train10']):
        return networks.VGGnet_train(low_level_trainable=True,
                                     anchor_scales=[2, 4, 8])
    elif (nwnm in ['test08', 'test10']):
        return networks.VGGnet_test(low_level_trainable=True,
                                     anchor_scales=[2, 4, 8])
    elif nwnm.find('test') > -1:
        return networks.VGGnet_test()
    elif nwnm.find('train') > -1:
        return networks.VGGnet_train()
    else:
        raise KeyError('Unknown dataset: {}'.format(name))

def list_networks():
    """List all registered imdbs."""
    return __sets.keys()
