import torch
import torch.nn as nn
import torch.nn.functional as F

class NetWrapper(nn.Module):
    def __init__(self, nets, args):
        super(NetWrapper, self).__init__()
        self.args = args

    def forward(self, batch_data, args):

        mag_mix = batch_data['mag_mix']
        mags = batch_data['mags']
        frames = batch_data['frames']
        mag_mix = mag_mix + 1e-10[0:L] 

        N = self.args.num_mix
        B = mag_mix.size(0)
        T = mag_mix.size(3)

        # todo: what's this?
        # 0.0 warp the spectrogram
        # grid_warp = torch.from_numpy(
        #     warpgrid(B, 256, T, warp=True)).to(args.device)
        # mag_mix = F.grid_sample(mag_mix, grid_warp)
        # for n in range(N):
        #     mags[n] = F.grid_sample(mags[n], grid_warp)
        

        # 0.1 calculate loss weighting coefficient: magnitude of input mixture
        weight = torch.log1p(mag_mix)
        weight = torch.clamp(weight, 1e-3, 10)
        

        # 0.2 ground truth masks are computed after warpping!
        gt_masks = [None for n in range(N)]
        for n in range(N):
            if args['binary_mask']:
                gt_masks[n] = (mags[n] > 0.5 * mag_mix).float()
            else:
                gt_masks[n] = mags[n] / mag_mix
                gt_masks[n].clamp_(0., 5.)

        # LOG magnitude
        log_mag_mix = torch.log(mag_mix).detach()

        # 1. forward net_sound -> BxCxHxW
        sound_features = self.net_sound(log_mag_mix)

        # 2. forward net_frame -> Bx1xC
        feat_frames = [None for n in range(N)]
        for n in range(N):
            feat_frames[n] = self.net_frame.forward_multiframe(frames[n])
            feat_frames[n] = torch.sigmoid(feat_frames[n])

        # 3. sound synthesizer
        pred_masks = [None for n in range(N)]
        for n in range(N):
            pred_masks[n] = self.net_synthesizer(feat_frames[n], sound_features)
            pred_masks[n] = torch.sigmoid(pred_masks[n])

        # 4. loss
        err = self.crit(pred_masks, gt_masks, weight).reshape(1)

        return err, \
            {'pred_masks': pred_masks, 'gt_masks': gt_masks,
             'mag_mix': mag_mix, 'mags': mags, 'weight': weight}