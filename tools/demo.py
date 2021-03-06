import _init_paths
import matplotlib
#matplotlib.use('pdf')
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import tensorflow as tf
from fast_rcnn.config import cfg
from fast_rcnn.test import im_detect, remove_embedded
from fast_rcnn.nms_wrapper import nms
from utils.timer import Timer
import numpy as np
import os, sys, cv2
import argparse
from networks.factory import get_network
from itertools import cycle

CLASSES =  ('__background__', # always index 0
                            '1_1', '1_2', '1_3', '2_2', '2_3', '3_3')

colors_ = cycle(['red', 'cyan', 'magenta', 'yellow'])

def vis_detections(im, class_name, dets,ax, thresh=0.5):
    """Draw detected bounding boxes."""
    inds = np.where(dets[:, -2] >= thresh)[0]
    if len(inds) == 0:
        thresh = np.max(dets[:, -2])
        inds = np.where(dets[:, -2] >= thresh)[0]

    for i in inds:
        bbox = dets[i, :4]
        score = dets[i, -2]
        if (class_name is None):
            class_name = CLASSES[int(dets[i, -1])]

        ax.add_patch(
            plt.Rectangle((bbox[0], bbox[1]),
                          bbox[2] - bbox[0],
                          bbox[3] - bbox[1], fill=False,
                          edgecolor=next(colors_), linewidth=2.5)
            )
        #cns = class_name.split('_')
        #class_name = '%sC%sP' % (cns[0], cns[1])
        ax.text(bbox[0], bbox[1] - 2,
                '{:s} {:.2f}'.format(class_name.replace('_', 'C_') + 'P', score),
                bbox=dict(facecolor='blue', alpha=0.4),
                fontsize=13, color='white')

    # ax.set_title(('{} detections with '
    #               'p({} | box) >= {:.1f}').format(class_name, class_name,
    #                                               thresh),
    #               fontsize=14)
    plt.axis('off')
    #plt.tight_layout()
    plt.draw()
    return len(inds)


def demo(sess, net, image_name, input_path, conf_thresh=0.8,
         save_vis_dir=None, remove_embedded_opt=0, eval_class=False):
    """
    Detect object classes in an image using pre-computed object proposals.
    eval_class: True - use traditional per class-based evaluation style
                False - use per RoI-based evaluation

    """

    # Load the demo image
    # im_file = os.path.join(cfg.DATA_DIR, 'demo', image_name)
    im_file = os.path.join(input_path, image_name)
    show_img_size = cfg.TEST.SCALES[0]
    if (not os.path.exists(im_file)):
        print('%s cannot be found' % (im_file))
        return -1
    #im_file = os.path.join('/home/corgi/Lab/label/pos_frame/ACCV/training/000001/',image_name)
    im = cv2.imread(im_file)

    # Detect all object classes and regress object bounds
    timer = Timer()
    timer.tic()
    scores, boxes = im_detect(sess, net, im, save_vis_dir=save_vis_dir,
                             img_name=os.path.splitext(image_name)[0])
    boxes *= float(show_img_size) / float(im.shape[0])
    #print("scores.shape = {0}, boxes.shape = {1}".format(scores.shape, boxes.shape))
    timer.toc()
    print ('Detection took {:.3f}s for '
           '{:d} object proposals').format(timer.total_time, boxes.shape[0])

    # Visualize detections for each class
    box_image_name = image_name.split('_')[0] + '_logminmax_radio.png'
    im_box_file = os.path.join(input_path, box_image_name)
    if (os.path.exists(im_box_file)):
        im = cv2.imread(im_box_file)

    my_dpi = 100
    fig = plt.figure()
    fig.set_size_inches(show_img_size / my_dpi, show_img_size / my_dpi)
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.set_xlim([0, show_img_size])
    ax.set_ylim([show_img_size, 0])
    #ax.set_aspect('equal')
    im = cv2.resize(im, (show_img_size, show_img_size))
    im = im[:, :, (2, 1, 0)]
    #fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(im, aspect='equal')

    #CONF_THRESH = 0.3
    NMS_THRESH = cfg.TEST.NMS #cfg.TEST.RPN_NMS_THRESH # 0.3

    tt_vis = 0
    bbox_img = []
    bscore_img = []
    if (eval_class):
        for cls_ind, cls in enumerate(CLASSES[1:]):
            cls_ind += 1 # because we skipped background
            cls_boxes = boxes[:, 4 * cls_ind : 4 * (cls_ind + 1)]
            cls_scores = scores[:, cls_ind]
            dets = np.hstack((cls_boxes,
                              cls_scores[:, np.newaxis]))#.astype(np.float32)
            keep = nms(dets, NMS_THRESH)
            #dets = dets[keep, :]
            dets = np.hstack((dets, np.ones([dets.shape[0], 1]) * cls_ind))
            if (dets.shape[0] > 0):
                bbox_img.append(dets)
                bscore_img.append(np.reshape(dets[:, -2], [-1, 1]))
    else:
        for eoi_ind, eoi in enumerate(boxes):
            eoi_scores = scores[eoi_ind, 1:] # skip background
            cls_ind = np.argmax(eoi_scores) + 1 # add the background index back
            cls_boxes = boxes[eoi_ind, 4 * cls_ind : 4 * (cls_ind + 1)]
            cls_scores = scores[eoi_ind, cls_ind]
            dets = np.hstack((np.reshape(cls_boxes, [1, -1]),
                              np.reshape(cls_scores, [-1, 1])))#.astype(np.float32)
            dets = np.hstack((dets, np.ones([dets.shape[0], 1]) * cls_ind))
            bbox_img.append(dets)
            bscore_img.append(np.reshape(dets[:, -2], [-1, 1]))

    boxes_im = np.vstack(bbox_img)
    scores_im = np.vstack(bscore_img)

    #if (not eval_class):
    # a numpy float is a C double, so need to use float32
    keep = nms(boxes_im[:, :-1].astype(np.float32), NMS_THRESH)
    boxes_im = boxes_im[keep, :]
    scores_im = scores_im[keep, :]

    if (remove_embedded_opt in [1, 2]):
        keep_indices = remove_embedded(boxes_im, scores_im, remove_option=remove_embedded_opt)
        print("removed %d boxes with option %d" % ((boxes_im.shape[0] - len(keep_indices)), remove_embedded_opt))
    else:
        keep_indices = range(boxes_im.shape[0])
    vis_detections(im, None, boxes_im[keep_indices, :], ax, thresh=conf_thresh)

    # if (tt_vis == 0):
    #     box_scores = scores[:, 1:]
    #     box_ind, cls_ind = np.unravel_index(np.argmax(box_scores), box_scores.shape)
    #     cls_ind += 1# because we skipped background
    #     cls = CLASSES[cls_ind]
    #     cls_boxes = boxes[box_ind:box_ind + 1, 4 * cls_ind : 4 * (cls_ind + 1)]
    #     cls_scores = scores[box_ind:box_ind + 1, cls_ind]
    #     dets = np.hstack((cls_boxes,
    #                       cls_scores[:, np.newaxis])).astype(np.float32)
    #     #keep = nms(dets, NMS_THRESH)
    #     #dets = dets[keep, :]
    #     vis_detections(im, cls, dets, ax, thresh=0.0)

    return 0

def parse_args():
    """Parse input arguments."""
    parser = argparse.ArgumentParser(description='Faster R-CNN demo')
    parser.add_argument('--gpu', dest='gpu_id', help='GPU device id to use [0]',
                        default=0, type=int)
    parser.add_argument('--cpu', dest='cpu_mode',
                        help='Use CPU mode (overrides --gpu)',
                        action='store_true')
    parser.add_argument('--net', dest='demo_net', help='Network to use [vgg16]',
                        default='VGGnet_test14')
    parser.add_argument('--model', dest='model', help='Model path',
                        default='/group/pawsey0129/cwu/rgz-faster-rcnn/output/faster_rcnn_end2end/rgz_2017_train/VGGnet_fast_rcnn-50000')
    parser.add_argument('--input', dest='input_path', help='Input PNG path',
                        default='/home/cwu/rgz-faster-rcnn/data/RGZdevkit2017/RGZ2017/PNGImages')
    parser.add_argument('--figure', dest='fig_path', help='Figure path',
                        default='/group/pawsey0129/cwu/output/22_result')
    parser.add_argument('--threshold', dest='conf_thresh', help='confidence threshold',
                        default=0.8, type=float)
    parser.add_argument('--imgindex', dest='img_index', help='Image index path',
                        default='/home/cwu/rgz-ml-ws/data/RGZdevkit2017/RGZ2017/ImageSets/Main/test14.txt')
    # parser.add_argument('--visdir', dest='save_vis_dir', help='Directory to save tensors for visual (e.g. weights, features)',
    #                     default=None)
    parser.add_argument('--imgsuffix', dest='img_suffix', default='_radio.png')

    parser.add_argument('--rmembedded', dest='remove_embedded_opt', help='Otion how to remove embedded cases',
                        default=0, type=int)

    parser.add_argument('--evaleoi', dest='eval_eoi',
                        help='evaluation based on EoI',
                        action='store_true', default=False)

    args = parser.parse_args()

    return args
if __name__ == '__main__':
    cfg.TEST.HAS_RPN = True  # Use RPN for proposals
    cfg.TEST.RPN_MIN_SIZE = 4
    cfg.TEST.RPN_POST_NMS_TOP_N = 5
    cfg.TEST.NMS = 0.3
    cfg.TEST.RPN_NMS_THRESH = 0.5

    args = parse_args()

    if args.model == ' ':
        raise IOError(('Error: Model not found.\n'))

    # init session
    sess = tf.Session(config=tf.ConfigProto(allow_soft_placement=True))
    # load network
    net = get_network(args.demo_net)
    # load model
    saver = tf.train.Saver(write_version=tf.train.SaverDef.V1)
    saver.restore(sess, args.model)

    #sess.run(tf.initialize_all_variables())

    print '\n\nLoaded network {:s}'.format(args.model)

    # Warmup on a dummy image
    im = 128 * np.ones((300, 300, 3), dtype=np.uint8)
    for i in xrange(2):
        _, _= im_detect(sess, net, im)

#     im_names = ['FIRSTJ094204.6+480448_logminmax_radio.png',  'FIRSTJ122547.1+594111_logminmax_radio.png',  'FIRSTJ145825.3+484239_logminmax_radio.png',  'FIRSTJ233909.5+113426_logminmax_radio.png',
# 'FIRSTJ094206.5+544626_logminmax_radio.png',  'FIRSTJ122547.8+051905_logminmax_radio.png',  'FIRSTJ145826.0+522419_logminmax_radio.png',  'FIRSTJ233912.1+105429_logminmax_radio.png',
# 'FIRSTJ094207.6+433848_logminmax_radio.png',  'FIRSTJ122549.6+163347_logminmax_radio.png',  'FIRSTJ145834.8+215228_logminmax_radio.png',  'FIRSTJ233921.6+064203_logminmax_radio.png',
# 'FIRSTJ094213.8+124534_logminmax_radio.png',  'FIRSTJ122552.1+634005_logminmax_radio.png',  'FIRSTJ145852.0+433709_logminmax_radio.png',  'FIRSTJ233939.4+020030_logminmax_radio.png',
# 'FIRSTJ094215.3+062820_logminmax_radio.png',  'FIRSTJ122555.1+153436_logminmax_radio.png',  'FIRSTJ145858.8+260859_logminmax_radio.png',  'FIRSTJ233954.0+115948_logminmax_radio.png',
# 'FIRSTJ094220.3+163949_logminmax_radio.png',  'FIRSTJ122600.9+084106_logminmax_radio.png',  'FIRSTJ145901.3+271124_logminmax_radio.png',  'FIRSTJ234004.0+021817_logminmax_radio.png',
# 'FIRSTJ094224.1+222307_logminmax_radio.png',  'FIRSTJ122608.8+473711_logminmax_radio.png',  'FIRSTJ145901.5+231026_logminmax_radio.png',  'FIRSTJ234235.1+103235_logminmax_radio.png',
# 'FIRSTJ094226.6+340231_logminmax_radio.png',  'FIRSTJ122609.5+584421_logminmax_radio.png',  'FIRSTJ145905.9+392409_logminmax_radio.png',  'FIRSTJ234247.4+142649_logminmax_radio.png',
# 'FIRSTJ094228.0+340243_logminmax_radio.png',  'FIRSTJ122612.8+062727_logminmax_radio.png',  'FIRSTJ145908.0+381509_logminmax_radio.png',  'FIRSTJ234253.1+094248_logminmax_radio.png']

    im_names = []
    with open(args.img_index, 'r') as fin:
        for line in fin:
            #print(line)
            fid = line.strip()
            #im_names.append(fid + '_radio.png')
            im_names.append(fid + args.img_suffix)

    for i, im_name in enumerate(im_names):
        #print '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~'
        #print 'Demo for data/demo/{}'.format(im_name)
        ret = demo(sess, net, im_name, args.input_path,
                    conf_thresh=args.conf_thresh, save_vis_dir=None,
                    remove_embedded_opt=args.remove_embedded_opt,
                    eval_class=(not args.eval_eoi))
                    #conf_thresh=args.conf_thresh, save_vis_dir=args.fig_path)
        if (-1 == ret):
            continue
        plt.savefig(os.path.join(args.fig_path, im_name.replace('.png', '_pred.png')), dpi=100)
        try:
            plt.close()
        except:
            pass
