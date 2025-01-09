import torch
import numpy as np

import torch.distributed as dist
from GEMZSL.utils.comm import *
from GEMZSL.engine.inferencer import eval_zs_gzsl

from torch.cuda.amp import autocast as autocast

# try:
#     from apex import amp
# except ImportError:
#     raise ImportError('Use APEX for multi-precision via apex.amp')


def reduce_loss_dict(loss_dict):
    """
    Reduce the loss dictionary from all processes so that process with rank
    0 has the averaged results. Returns a dict with the same fields as
    loss_dict, after reduction.
    """
    world_size = get_world_size()
    if world_size < 2:
        return loss_dict
    with torch.no_grad():
        loss_names = []
        all_losses = []
        for k in sorted(loss_dict.keys()):
            loss_names.append(k)
            all_losses.append(loss_dict[k])
        all_losses = torch.stack(all_losses, dim=0)
        dist.reduce(all_losses, dst=0)
        if dist.get_rank() == 0:
            # only main process gets accumulated, so only divide by
            # world_size in this case
            all_losses /= world_size
        reduced_losses = {k: v for k, v in zip(loss_names, all_losses)}
    return reduced_losses

def do_train(
        model,
        tr_dataloader,
        tu_loader,
        ts_loader,
        res,
        optimizer,
        scheduler,
        lamd,
        test_gamma,
        device,
        max_epoch,
        model_file_path,
        scaler,
    ):

    best_performance = [0, 0, 0, 0]
    best_epoch = -1

    att_seen = res['att_seen'].to(device)


    model.train()

    for epoch in range(0, max_epoch):
        print("开始训练")


        reg1_loss_epoch = []
        cpt1_loss_epoch = []
        reg2_loss_epoch = []
        cpt2_loss_epoch = []

        cls3_loss_epoch = []
        reg3_loss_epoch = []
        ad3_loss_epoch = []
        cpt3_loss_epoch = []

        cls4_loss_epoch = []
        reg4_loss_epoch = []
        ad4_loss_epoch = []
        cpt4_loss_epoch = []

        clsx4_loss_epoch = []
        regx4_loss_epoch = []
        adx4_loss_epoch = []
        cptx4_loss_epoch = []

        for iteration, (batch_img, batch_att, batch_label) in enumerate(tr_dataloader):
            batch_img = batch_img.to(device)
            batch_att = batch_att.to(device)
            batch_label = batch_label.to(device)

            with autocast():
                loss_dict3, loss_dict4 = model(x=batch_img, att=batch_att, label=batch_label, seen_att=att_seen, )
                # loss_dict1, loss_dict2, loss_dict3, loss_dict4 = model(x=batch_img, att=batch_att, label=batch_label, seen_att=att_seen, )

            scale = loss_dict4['scale']
            loss_dict4.pop('scale')

            # reduce losses over all GPUs for logging purposes
            # layer1
            # loss_dict_reduced1 = loss_dict1
            # lreg1 = loss_dict_reduced1['Reg_loss']
            # lcls1 = loss_dict_reduced1['Cls_loss']
            # lad1 = loss_dict_reduced1['AD_loss']
            # # lcpt1 = loss_dict_reduced1['CPT_loss']
            # loss1 = lcls1 + lamd[1] * lreg1 + lamd[2] * lad1

            # layer2
            # loss_dict_reduced2 = loss_dict2
            # lreg2 = loss_dict_reduced2['Reg_loss']
            # lcls2 = loss_dict_reduced2['Cls_loss']
            # lad2 = loss_dict_reduced2['AD_loss']
            # # lcpt2 = loss_dict_reduced2['CPT_loss']
            # loss2 = lcls2 + lamd[1] * lreg2 + lamd[2] * lad2

            # layer3
            loss_dict_reduced3 = loss_dict3
            lreg3 = loss_dict_reduced3['Reg_loss']
            lcls3 = loss_dict_reduced3['Cls_loss']
            lad3 = loss_dict_reduced3['AD_loss']
            # lpart3 = loss_dict_reduced3['part_loss']
            # lcpt3 = loss_dict_reduced3['CPT_loss']
            loss3 = lcls3 + lamd[1] * lreg3 + lamd[2] * lad3

            loss_dict_reduced4 = loss_dict4
            lreg4 = loss_dict_reduced4['Reg_loss']
            lcls4 = loss_dict_reduced4['Cls_loss']
            lad4 = loss_dict_reduced4['AD_loss']
            # lpart4 = loss_dict_reduced4['part_loss']
            # lcpt4 = loss_dict_reduced4['CPT_loss']
            loss4 = lcls4 + lamd[1] * lreg4 + lamd[2] * lad4

            # loss_dict_reducedx4 = loss_dictx4
            # lregx4 = loss_dict_reducedx4['Reg_loss']
            # lclsx4 = loss_dict_reducedx4['Cls_loss']
            # ladx4 = loss_dict_reducedx4['AD_loss']
            # lcptx4 = loss_dict_reducedx4['CPT_loss']
            # lossx4 = lclsx4 + lamd[1] * lregx4 + lamd[2] * ladx4 + lamd[3] * lcptx4

            # loss = (loss1 + loss2 + loss3 + loss4)
            loss = loss3 + loss4

            optimizer.zero_grad()
            # scaler.scale(loss).backward()
            scaler.scale(loss).backward(retain_graph=True)
            scaler.step(optimizer)
            scaler.update()

            # model.fuse_weight3_clamped.data.clamp_(0.0, 1.0)
            # model.fuse_weight4_clamped.data.clamp_(0.0, 1.0)

            # model.part_weight3.data.clamp_(0.0, 1.0)
            # model.part_weight4.data.clamp_(0.0, 1.0)

            # model.pip3.weight.data.clamp_(0.0, 1.0)
            # model.pip4.weight.data.clamp_(0.0, 1.0)

            # reg1_loss_epoch.append(lreg1.item())
            # cpt1_loss_epoch.append(lcpt1.item())
            #
            # reg2_loss_epoch.append(lreg2.item())
            # cpt2_loss_epoch.append(lcpt2.item())

            cls3_loss_epoch.append(lcls3.item())
            reg3_loss_epoch.append(lreg3.item())
            ad3_loss_epoch.append(lad3.item())
            # cpt3_loss_epoch.append(lcpt3.item())

            cls4_loss_epoch.append(lcls4.item())
            reg4_loss_epoch.append(lreg4.item())
            ad4_loss_epoch.append(lad4.item())
            # cpt4_loss_epoch.append(lcpt4.item())

            # clsx4_loss_epoch.append(lclsx4.item())
            # regx4_loss_epoch.append(lregx4.item())
            # adx4_loss_epoch.append(ladx4.item())
            # cptx4_loss_epoch.append(lcptx4.item())


        scheduler.step()
        # 更改学习率

        if is_main_process():
            # reg1_loss_epoch_mean = sum(reg1_loss_epoch) / len(reg1_loss_epoch)
            # cpt1_loss_epoch_mean = sum(cpt1_loss_epoch) / len(cpt1_loss_epoch)
            #
            # reg2_loss_epoch_mean = sum(reg2_loss_epoch) / len(reg2_loss_epoch)
            # cpt2_loss_epoch_mean = sum(cpt2_loss_epoch) / len(cpt2_loss_epoch)

            cls3_loss_epoch_mean = sum(cls3_loss_epoch)/len(cls3_loss_epoch)
            reg3_loss_epoch_mean = sum(reg3_loss_epoch)/len(reg3_loss_epoch)
            ad3_loss_epoch_mean = sum(ad3_loss_epoch)/len(ad3_loss_epoch)
            # cpt3_loss_epoch_mean = sum(cpt3_loss_epoch)/len(cpt3_loss_epoch)


            cls4_loss_epoch_mean = sum(cls4_loss_epoch)/len(cls4_loss_epoch)
            reg4_loss_epoch_mean = sum(reg4_loss_epoch)/len(reg4_loss_epoch)
            ad4_loss_epoch_mean = sum(ad4_loss_epoch)/len(ad4_loss_epoch)
            # cpt4_loss_epoch_mean = sum(cpt4_loss_epoch)/len(cpt4_loss_epoch)

            # clsx4_loss_epoch_mean = sum(clsx4_loss_epoch)/len(clsx4_loss_epoch)
            # regx4_loss_epoch_mean = sum(regx4_loss_epoch)/len(regx4_loss_epoch)
            # adx4_loss_epoch_mean = sum(adx4_loss_epoch)/len(adx4_loss_epoch)
            # cptx4_loss_epoch_mean = sum(cptx4_loss_epoch)/len(cptx4_loss_epoch)

            # print(f'debug_cls3_loss_epoch: {cls3_loss_epoch}')
            # print(f'debug_cls3_sum: {sum(cls3_loss_epoch)}')
            # print(f'debug_cls3_len: {len(cls3_loss_epoch)}')
            # print(f'debug_cls3: {cls3_loss_epoch_mean}')

            # print(f'debug_cls4_loss_epoch: {cls4_loss_epoch}')
            # print(f'debug_cls4_sum: {sum(cls4_loss_epoch)}')
            # print(f'debug_cls4_len: {len(cls4_loss_epoch)}')
            # print(f'debug_cls4: {cls4_loss_epoch_mean}')

            log_info = 'epoch: %d  |   lr: %.6f' % \
                       (epoch + 1,  optimizer.param_groups[0]["lr"])
            # log_info1 = 'layer1 | reg_loss: %.4f, cpt_loss: %.4f' % \
            #            ( reg1_loss_epoch_mean, cpt1_loss_epoch_mean)
            # log_info2 = 'layer2 | reg_loss: %.4f, cpt_loss: %.4f' % \
            #            (reg2_loss_epoch_mean, cpt2_loss_epoch_mean)
            log_info3 = 'layer3 | cls_loss: %.4f , reg_loss: %.4f, ad_loss: %.4f' % \
                       (cls3_loss_epoch_mean, reg3_loss_epoch_mean, ad3_loss_epoch_mean)
            log_info4 = 'layer4 | cls_loss: %.4f , reg_loss: %.4f, ad_loss: %.4f' % \
                       (cls4_loss_epoch_mean, reg4_loss_epoch_mean, ad4_loss_epoch_mean)
            # log_infox4 = 'layer4 | cls_loss: %.4f , reg_loss: %.4f, cpt_loss: %.4f, ad_loss: %.4f' % \
            #            (clsx4_loss_epoch_mean, regx4_loss_epoch_mean, cptx4_loss_epoch_mean, adx4_loss_epoch_mean)
            print(log_info)
            # print(log_info1)
            # print(log_info2)
            print(log_info3)
            print(log_info4)
            # print(log_infox4)

        synchronize()
        # 分布训练的同步文件
        torch.cuda.empty_cache()
        acc_zsl, acc_unseen, acc_seen, H = eval_zs_gzsl(
            tu_loader,
            ts_loader,
            res,
            model,
            test_gamma,
            device)


        if is_main_process():
            for i in range(0, 11):
                print('fuse%.0f: zsl: %.4f, gzsl: seen=%.4f, unseen=%.4f, h=%.4f' % (i, acc_zsl[i], acc_seen[i], acc_unseen[i], H[i]))

                if H[i] > best_performance[-1]:
                    # 储存的是H最高的
                    best_performance[1:] = [acc_seen[i], acc_unseen[i], H[i]]
                    # best_epoch = epoch + 1
                    # data = {}
                    # data["model"] = model.state_dict()
                    # torch.save(data, model_file_path)
                    # print('save model: ' + model_file_path)

                if acc_zsl[i] > best_performance[0]:
                    best_performance[0] = acc_zsl[i]
                    best_epoch = epoch + 1
                    data = {}
                    data["model"] = model.state_dict()
                    torch.save(data, model_file_path)
                    print('save model: ' + model_file_path)

        # if is_main_process():
        #     print('zsl: %.4f, gzsl: seen=%.4f, unseen=%.4f, h=%.4f' % (acc_zs, acc_seen, acc_novel, H))
        #
        # if H > best_performance[-1]:
        #     # 储存的是H最高的
        #     best_performance[1:] = [acc_seen, acc_novel, H]
        #     # best_epoch = epoch + 1
        #     # data = {}
        #     # data["model"] = model.state_dict()
        #     # torch.save(data, model_file_path)
        #     # print('save model: ' + model_file_path)
        #
        # if acc_zs > best_performance[0]:
        #     best_performance[0] = acc_zs
        #     best_epoch = epoch + 1
        #     data = {}
        #     data["model"] = model.state_dict()
        #     torch.save(data, model_file_path)
        #     print('save model: ' + model_file_path)

    if is_main_process():
        print("best: ep: %d" % best_epoch)
        print('zsl: %.4f, gzsl: seen=%.4f, unseen=%.4f, h=%.4f' % tuple(best_performance))