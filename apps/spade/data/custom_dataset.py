"""
Copyright (C) 2019 NVIDIA Corporation.  All rights reserved.
Licensed under the CC BY-NC-SA 4.0 license (https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode).
"""

from .pix2pix_dataset import Pix2pixDataset
from .image_folder import make_dataset


class CustomDataset(Pix2pixDataset):
    """ Dataset that loads images from directories
        Use option --label_dir, --image_dir, --instance_dir to specify the directories.
        The images in the directories are sorted in alphabetical order and paired in order.
    """

    @staticmethod
    def modify_commandline_options(parser, is_train):
        parser = Pix2pixDataset.modify_commandline_options(parser, is_train)
        parser.set_defaults(preprocess_mode='custom')
        load_size = 3840
        parser.set_defaults(load_size=load_size)
        parser.set_defaults(crop_size=3840)
        parser.set_defaults(aspect_ratio=3.0)
        parser.set_defaults(display_winsize=256)
        parser.set_defaults(label_nc=19)
        parser.set_defaults(contain_dontcare_label=True)
        parser.set_defaults(no_instance=True)
        parser.set_defaults(num_upsampling_layers='most')
        parser.set_defaults(ngf=96)
        parser.set_defaults(gpu_ids="0")
        parser.set_defaults(batchSize=1)
        parser.set_defaults(label_dir='datasets/tmpl/masks')
        parser.set_defaults(image_dir='datasets/tmpl/images')

        parser.add_argument('--instance_dir', type=str, default='', help='path to the directory that contains instance maps. Leave black if not exists')
        return parser

    def get_paths(self, opt):
        label_dir = opt.label_dir
        label_paths = make_dataset(label_dir, recursive=False, read_cache=True)

        image_dir = opt.image_dir
        image_paths = make_dataset(image_dir, recursive=False, read_cache=True)

        if len(opt.instance_dir) > 0:
            instance_dir = opt.instance_dir
            instance_paths = make_dataset(instance_dir, recursive=False, read_cache=True)
        else:
            instance_paths = []

        assert len(label_paths) == len(image_paths), "The #images in %s and %s do not match. Is there something wrong?"

        return label_paths, image_paths, instance_paths
