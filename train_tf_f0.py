import tensorflow as tf


import matplotlib.pyplot as plt

import os
import sys
import time
import numpy as np
from six.moves import xrange  # pylint: disable=redefined-builtin
import h5py

import config
from data_pipeline import data_gen
import modules_tf as modules
import utils
from reduce import mgc_to_mfsc


def binary_cross(p,q):
    return -(p * tf.log(q + 1e-12) + (1 - p) * tf.log( 1 - q + 1e-12))

def train(_):
    stat_file = h5py.File(config.stat_dir+'stats.hdf5', mode='r')
    max_feat = np.array(stat_file["feats_maximus"])
    min_feat = np.array(stat_file["feats_minimus"])
    with tf.Graph().as_default():
        
        input_placeholder = tf.placeholder(tf.float32, shape=(config.batch_size,config.max_phr_len,config.input_features),name='input_placeholder')
        tf.summary.histogram('inputs', input_placeholder)
        target_placeholder = tf.placeholder(tf.float32, shape=(config.batch_size,config.max_phr_len,3),name='target_placeholder')
        tf.summary.histogram('targets', target_placeholder)

        with tf.variable_scope('First_Model') as scope:
            f0, f0_1, vuv = modules.f0_network(input_placeholder)

            # tf.summary.histogram('initial_output', op)

            # tf.summary.histogram('harm', harm)

            # tf.summary.histogram('ap', ap)

            tf.summary.histogram('f0', f0)

            tf.summary.histogram('vuv', vuv)

        # initial_loss = tf.reduce_sum(tf.abs(op - target_placeholder[:,:,:60])*np.linspace(1.0,0.7,60)*(1-target_placeholder[:,:,-1:]))

        # harm_loss = tf.reduce_sum(tf.abs(harm - target_placeholder[:,:,:60])*np.linspace(1.0,0.7,60)*(1-target_placeholder[:,:,-1:]))

        # ap_loss = tf.reduce_sum(tf.abs(ap - target_placeholder[:,:,60:-2])*(1-target_placeholder[:,:,-1:]))

        f0_loss_1 = tf.reduce_sum(tf.abs(f0 - target_placeholder[:,:,-3:-2])*(1-target_placeholder[:,:,-1:])) 

        f0_loss_2 = tf.reduce_sum(tf.abs(f0_1 - target_placeholder[:,:,-2:-1])*(1-target_placeholder[:,:,-1:])) 

        # vuv_loss = tf.reduce_sum(tf.nn.sigmoid_cross_entropy_with_logits(labels=, logits=vuv))

        vuv_loss = tf.reduce_sum(binary_cross(target_placeholder[:,:,-1:],vuv))

        loss = f0_loss_1 + vuv_loss + f0_loss_2

        # initial_summary = tf.summary.scalar('initial_loss', initial_loss)

        # harm_summary = tf.summary.scalar('harm_loss', harm_loss)

        # ap_summary = tf.summary.scalar('ap_loss', ap_loss)

        f0_summary_1 = tf.summary.scalar('f0_loss_1', f0_loss_1)

        f0_summary_2 = tf.summary.scalar('f0_loss_2', f0_loss_2)

        vuv_summary = tf.summary.scalar('vuv_loss', vuv_loss)

        loss_summary = tf.summary.scalar('total_loss', loss)

        global_step = tf.Variable(0, name='global_step', trainable=False)

        optimizer = tf.train.AdamOptimizer(learning_rate = config.init_lr)

        # optimizer_f0 = tf.train.AdamOptimizer(learning_rate = config.init_lr)

        train_function = optimizer.minimize(loss, global_step= global_step)

        # train_f0 = optimizer.minimize(f0_loss, global_step= global_step)

        # train_harm = optimizer.minimize(harm_loss, global_step= global_step)

        # train_ap = optimizer.minimize(ap_loss, global_step= global_step)

        # train_f0 = optimizer.minimize(f0_loss, global_step= global_step)

        # train_vuv = optimizer.minimize(vuv_loss, global_step= global_step)

        summary = tf.summary.merge_all()

        init_op = tf.group(tf.global_variables_initializer(), tf.local_variables_initializer())
        saver = tf.train.Saver(max_to_keep= config.max_models_to_keep)
        sess = tf.Session()

        sess.run(init_op)

        ckpt = tf.train.get_checkpoint_state(config.log_dir)

        if ckpt and ckpt.model_checkpoint_path:
            print("Using the model in %s"%ckpt.model_checkpoint_path)
            saver.restore(sess, ckpt.model_checkpoint_path)


        train_summary_writer = tf.summary.FileWriter(config.log_dir+'train/', sess.graph)
        val_summary_writer = tf.summary.FileWriter(config.log_dir+'val/', sess.graph)

        
        start_epoch = int(sess.run(tf.train.get_global_step())/(config.batches_per_epoch_train))

        print("Start from: %d" % start_epoch)
        f0_accs = []
        for epoch in xrange(start_epoch, config.num_epochs):
            val_f0_accs_1 = []
            val_f0_accs_2 = []


            data_generator = data_gen()
            start_time = time.time()

            epoch_loss_harm = 0
            epoch_loss_ap = 0
            epoch_loss_f0_1 = 0
            epoch_loss_f0_2 = 0
            epoch_loss_vuv = 0
            epoch_total_loss = 0
            # epoch_initial_loss = 0

            epoch_loss_harm_val = 0
            epoch_loss_ap_val = 0
            epoch_loss_f0_val_1 = 0
            epoch_loss_f0_val_2 = 0
            epoch_loss_vuv_val = 0
            epoch_total_loss_val = 0
            # epoch_initial_loss_val = 0

            if config.use_gan:
                epoch_loss_generator_GAN = 0
                epoch_loss_generator_diff = 0
                epoch_loss_discriminator_real = 0
                epoch_loss_discriminator_fake = 0

                val_epoch_loss_generator_GAN = 0
                val_epoch_loss_generator_diff = 0
                val_epoch_loss_discriminator_real = 0
                val_epoch_loss_discriminator_fake = 0

            batch_num = 0
            batch_num_val = 0
            val_generator = data_gen(mode='val')

            # val_generator = get_batches(train_filename=config.h5py_file_val, batches_per_epoch=config.batches_per_epoch_val)

            with tf.variable_scope('Training'):

                for voc, feat in data_generator:

                    _, step_loss_f0_1,step_loss_f0_2, step_loss_vuv, step_total_loss = sess.run([train_function, 
                        f0_loss_1,f0_loss_2, vuv_loss, loss], feed_dict={input_placeholder: voc,target_placeholder: feat})
                    # _, step_loss_f0 = sess.run([train_f0, f0_loss], feed_dict={input_placeholder: voc,target_placeholder: feat})
                    
                    if config.use_gan:
                        _, step_dis_loss_real, step_dis_loss_fake = sess.run([d_optimizer, D_loss_real,D_loss_fake], feed_dict={input_placeholder: voc,target_placeholder: feat})
                        _, step_gen_loss_GAN, step_gen_loss_diff = sess.run([g_optimizer, G_loss_GAN, G_loss_diff], feed_dict={input_placeholder: voc,target_placeholder: feat})
                    # else :
                    #     _, step_dis_loss_real, step_dis_loss_fake = sess.run([d_optimizer_grad, D_loss_real,D_loss_fake], feed_dict={input_placeholder: voc,target_placeholder: feat})
                    #     _, step_gen_loss_diff = sess.run([g_optimizer_diff, G_loss_diff], feed_dict={input_placeholder: voc,target_placeholder: feat})
                    #     step_gen_loss_GAN = 0




                    # _, step_loss_harm = sess.run([train_harm, harm_loss], feed_dict={input_placeholder: voc,target_placeholder: feat})
                    # _, step_loss_ap = sess.run([train_ap, ap_loss], feed_dict={input_placeholder: voc,target_placeholder: feat})
                    # _, step_loss_f0 = sess.run([train_f0, f0_loss], feed_dict={input_placeholder: voc,target_placeholder: feat})
                    # _, step_loss_vuv = sess.run([train_vuv, vuv_loss], feed_dict={input_placeholder: voc,target_placeholder: feat})

                    # epoch_initial_loss+=step_initial_loss
                    # epoch_loss_harm+=step_loss_harm
                    # epoch_loss_ap+=step_loss_ap
                    epoch_loss_f0_1+=step_loss_f0_1
                    epoch_loss_f0_2+=step_loss_f0_2
                    epoch_loss_vuv+=step_loss_vuv
                    epoch_total_loss+=step_total_loss

                    if config.use_gan:

                        epoch_loss_generator_GAN+=step_gen_loss_GAN
                        epoch_loss_generator_diff+=step_gen_loss_diff
                        epoch_loss_discriminator_real+=step_dis_loss_real
                        epoch_loss_discriminator_fake+=step_dis_loss_fake



                    utils.progress(batch_num,config.batches_per_epoch_train, suffix = 'training done')
                    batch_num+=1


                # epoch_initial_loss = epoch_initial_loss/(config.batches_per_epoch_train *config.batch_size*config.max_phr_len*60)
                # epoch_loss_harm = epoch_loss_harm/(config.batches_per_epoch_train *config.batch_size*config.max_phr_len*60)
                # epoch_loss_ap = epoch_loss_ap/(config.batches_per_epoch_train *config.batch_size*config.max_phr_len*4)
                epoch_loss_f0_1 = epoch_loss_f0_1/(config.batches_per_epoch_train *config.batch_size*config.max_phr_len)
                epoch_loss_f0_2 = epoch_loss_f0_2/(config.batches_per_epoch_train *config.batch_size*config.max_phr_len)
                epoch_loss_vuv = epoch_loss_vuv/(config.batches_per_epoch_train *config.batch_size*config.max_phr_len)
                epoch_total_loss = epoch_total_loss/(config.batches_per_epoch_train *config.batch_size*config.max_phr_len*3)

                if config.use_gan:

                    epoch_loss_generator_GAN = epoch_loss_generator_GAN/(config.batches_per_epoch_train *config.batch_size)
                    epoch_loss_generator_diff = epoch_loss_generator_diff/(config.batches_per_epoch_train *config.batch_size*config.max_phr_len*60)
                    epoch_loss_discriminator_real = epoch_loss_discriminator_real/(config.batches_per_epoch_train *config.batch_size)
                    epoch_loss_discriminator_fake = epoch_loss_discriminator_fake/(config.batches_per_epoch_train *config.batch_size)
                

                summary_str = sess.run(summary, feed_dict={input_placeholder: voc,target_placeholder: feat})
                train_summary_writer.add_summary(summary_str, epoch)
                # summary_writer.add_summary(summary_str_val, epoch)
                train_summary_writer.flush()

            with tf.variable_scope('Validation'):

                for voc, feat,nchunks_in, lent, county, max_count in val_generator:

                    if (epoch + 1) % config.print_every == 0 or (epoch + 1) == config.num_epochs:

                        if county == 1:
                            f0_gt = []
                            vuv_gt = []
                            f0_output_1 = []
                            f0_output_2 = []

                        f0_op_1, f0_op_2 = sess.run([f0,f0_1],feed_dict={input_placeholder: voc,target_placeholder: feat})
                        f0_output_1.append(f0_op_1)
                        f0_output_2.append(f0_op_2)
                        f0_gt.append(feat[:,:,-2:-1])
                        vuv_gt.append(feat[:,:,-1:])

                        if county == max_count:
                            f0_output_1 = utils.overlapadd(np.array(f0_output_1), nchunks_in) 
                            f0_output_2 = utils.overlapadd(np.array(f0_output_2), nchunks_in) 
                            f0_gt = utils.overlapadd(np.array(f0_gt), nchunks_in) 
                            vuv_gt = utils.overlapadd(np.array(vuv_gt), nchunks_in) 

                            f0_output_1 = f0_output_1[:lent]
                            f0_output_2 = f0_output_2[:lent]
                            f0_gt = f0_gt[:lent]
                            vuv_gt = vuv_gt[:lent]

                            f0_output_1 = f0_output_1*((max_feat[-2]-min_feat[-2])+min_feat[-2])*(1-vuv_gt)
                            f0_output_2 = f0_output_2*((max_feat[-2]-min_feat[-2])+min_feat[-2])*(1-vuv_gt)
                            f0_gt = f0_gt*((max_feat[-2]-min_feat[-2])+min_feat[-2])*(1-vuv_gt)

                            # f0_output_1[f0_output_1 == 0] = np.nan

                            # f0_gt[f0_gt == 0] = np.nan

                            f0_difference_1 = np.nan_to_num(abs(f0_gt-f0_output_1))
                            f0_greater_1 = np.where(f0_difference_1>config.f0_threshold)
                            diff_per_1 = f0_greater_1[0].shape[0]/len(f0_output_1)
                            val_f0_accs_1.append(1 - diff_per_1)

                            f0_difference_2 = np.nan_to_num(abs(f0_gt-f0_output_2))
                            f0_greater_2 = np.where(f0_difference_2>config.f0_threshold)
                            diff_per_2 = f0_greater_2[0].shape[0]/len(f0_output_2)
                            val_f0_accs_2.append(1 - diff_per_2)
                
                        # import pdb;pdb.set_trace()






                    # step_initial_loss_val = sess.run(initial_loss, feed_dict={input_placeholder: voc,target_placeholder: feat})
                    # step_loss_harm_val = sess.run(harm_loss, feed_dict={input_placeholder: voc,target_placeholder: feat})
                    # step_loss_ap_val = sess.run(ap_loss, feed_dict={input_placeholder: voc,target_placeholder: feat})
                    step_loss_f0_val_1 = sess.run(f0_loss_1, feed_dict={input_placeholder: voc,target_placeholder: feat})
                    step_loss_f0_val_2 = sess.run(f0_loss_2, feed_dict={input_placeholder: voc,target_placeholder: feat})
                    step_loss_vuv_val = sess.run(vuv_loss, feed_dict={input_placeholder: voc,target_placeholder: feat})
                    step_total_loss_val = sess.run(loss, feed_dict={input_placeholder: voc,target_placeholder: feat})

                    if config.use_gan:
                        step_gen_loss_GAN, step_gen_loss_diff = sess.run([G_loss_GAN, G_loss_diff], feed_dict={input_placeholder: voc,target_placeholder: feat})
                        step_dis_loss_real,step_dis_loss_fake = sess.run([D_loss_real,D_loss_fake], feed_dict={input_placeholder: voc,target_placeholder: feat})

                    # epoch_initial_loss_val+=step_initial_loss_val
                    # epoch_loss_harm_val+=step_loss_harm_val
                    # epoch_loss_ap_val+=step_loss_ap_val
                    epoch_loss_f0_val_1+=step_loss_f0_val_1
                    epoch_loss_f0_val_2+=step_loss_f0_val_2
                    epoch_loss_vuv_val+=step_loss_vuv_val
                    epoch_total_loss_val+=step_total_loss_val

                    if config.use_gan:

                        val_epoch_loss_generator_GAN += step_gen_loss_GAN
                        val_epoch_loss_generator_diff += step_gen_loss_diff
                        val_epoch_loss_discriminator_real += step_dis_loss_real
                        val_epoch_loss_discriminator_fake += step_dis_loss_fake

                    utils.progress(batch_num_val,config.batches_per_epoch_val, suffix = 'validiation done')
                    batch_num_val+=1
                if (epoch + 1) % config.print_every == 0 or (epoch + 1) == config.num_epochs:    
                    f0_accs.append(np.mean(val_f0_accs_2))

                # epoch_initial_loss_val = epoch_initial_loss_val/(config.batches_per_epoch_val *config.batch_size*config.max_phr_len*60)
                # epoch_loss_harm_val = epoch_loss_harm_val/(batch_num_val *config.batch_size*config.max_phr_len*60)
                # epoch_loss_ap_val = epoch_loss_ap_val/(batch_num_val *config.batch_size*config.max_phr_len*4)
                epoch_loss_f0_val_1 = epoch_loss_f0_val_1/(batch_num_val *config.batch_size*config.max_phr_len)
                epoch_loss_f0_val_2 = epoch_loss_f0_val_2/(batch_num_val *config.batch_size*config.max_phr_len)
                epoch_loss_vuv_val = epoch_loss_vuv_val/(batch_num_val *config.batch_size*config.max_phr_len)
                epoch_total_loss_val = epoch_total_loss_val/(batch_num_val *config.batch_size*config.max_phr_len*66)

                if config.use_gan:

                    val_epoch_loss_generator_GAN = val_epoch_loss_generator_GAN/(config.batches_per_epoch_val *config.batch_size)
                    val_epoch_loss_generator_diff = val_epoch_loss_generator_diff/(config.batches_per_epoch_val *config.batch_size*config.max_phr_len*60)
                    val_epoch_loss_discriminator_real = val_epoch_loss_discriminator_real/(config.batches_per_epoch_val *config.batch_size)
                    val_epoch_loss_discriminator_fake = val_epoch_loss_discriminator_fake/(config.batches_per_epoch_val *config.batch_size)

                summary_str = sess.run(summary, feed_dict={input_placeholder: voc,target_placeholder: feat})
                val_summary_writer.add_summary(summary_str, epoch)
                # summary_writer.add_summary(summary_str_val, epoch)
                val_summary_writer.flush()

            duration = time.time() - start_time

            np.save('./ikala_eval/accuracies', f0_accs)

            if (epoch+1) % config.print_every == 0:
                print('epoch %d: F0 Training Loss = %.10f (%.3f sec)' % (epoch+1, epoch_loss_f0_1, duration))
                # print('        : Ap Training Loss = %.10f ' % (epoch_loss_ap))
                # print('        : F0 Training Loss = %.10f ' % (epoch_loss_f0))
                print('        : VUV Training Loss = %.10f ' % (epoch_loss_vuv))
                # print('        : Initial Training Loss = %.10f ' % (epoch_initial_loss))

                if config.use_gan:

                    print('        : Gen GAN Training Loss = %.10f ' % (epoch_loss_generator_GAN))
                    print('        : Gen diff Training Loss = %.10f ' % (epoch_loss_generator_diff))
                    print('        : Discriminator Training Loss Real = %.10f ' % (epoch_loss_discriminator_real))
                    print('        : Discriminator Training Loss Fake = %.10f ' % (epoch_loss_discriminator_fake))

                # print('        : Harm Validation Loss = %.10f ' % (epoch_loss_harm_val))
                # print('        : Ap Validation Loss = %.10f ' % (epoch_loss_ap_val))
                print('        : F0 Validation Loss_1 = %.10f ' % (epoch_loss_f0_val_1))
                print('        : F0 Validation Loss_2 = %.10f ' % (epoch_loss_f0_val_2))
                print('        : VUV Validation Loss = %.10f ' % (epoch_loss_vuv_val))
                
                if (epoch + 1) % config.print_every == 0 or (epoch + 1) == config.num_epochs:
                    print('        : Mean F0 IKala Accuracy_1  = %.10f ' % (np.mean(val_f0_accs_1)))
                    print('        : Mean F0 IKala Accuracy_2  = %.10f ' % (np.mean(val_f0_accs_2)))

                # print('        : Mean F0 IKala Accuracy = '+'%{1:.{0}f}%'.format(np.mean(val_f0_accs)))
                # print('        : Initial Validation Loss = %.10f ' % (epoch_initial_loss_val))

                if config.use_gan:

                    print('        : Gen GAN Validation Loss = %.10f ' % (val_epoch_loss_generator_GAN))
                    print('        : Gen diff Validation Loss = %.10f ' % (val_epoch_loss_generator_diff))
                    print('        : Discriminator Validation Loss Real = %.10f ' % (val_epoch_loss_discriminator_real))
                    print('        : Discriminator Validation Loss Fake = %.10f ' % (val_epoch_loss_discriminator_fake))


            if (epoch + 1) % config.save_every == 0 or (epoch + 1) == config.num_epochs:
                # utils.list_to_file(val_f0_accs,'./ikala_eval/accuracies_'+str(epoch+1)+'.txt')
                checkpoint_file = os.path.join(config.log_dir, 'model.ckpt')
                saver.save(sess, checkpoint_file, global_step=epoch)


def synth_file(file_name, file_path=config.wav_dir, show_plots=True, save_file=True):
    if file_name.startswith('ikala'):
        file_name = file_name[6:]
        file_path = config.wav_dir
        utils.write_ori_ikala(os.path.join(file_path,file_name),file_name)
        mode =0
    elif file_name.startswith('mir'):
        file_name = file_name[4:]
        file_path = config.wav_dir_mir
        utils.write_ori_ikala(os.path.join(file_path,file_name),file_name)
        mode =0
    elif file_name.startswith('med'):
        file_name = file_name[4:]
        file_path = config.wav_dir_med
        utils.write_ori_med(os.path.join(file_path,file_name),file_name)
        mode =2

    stat_file = h5py.File(config.stat_dir+'stats.hdf5', mode='r')

    max_feat = np.array(stat_file["feats_maximus"])
    min_feat = np.array(stat_file["feats_minimus"])
    max_voc = np.array(stat_file["voc_stft_maximus"])
    min_voc = np.array(stat_file["voc_stft_minimus"])
    max_back = np.array(stat_file["back_stft_maximus"])
    min_back = np.array(stat_file["back_stft_minimus"])
    max_mix = np.array(max_voc)+np.array(max_back)

    with tf.Graph().as_default():
        
        input_placeholder = tf.placeholder(tf.float32, shape=(config.batch_size,config.max_phr_len,config.input_features),name='input_placeholder')


        with tf.variable_scope('First_Model') as scope:
            f0, vuv = modules.nr_wavenet(input_placeholder)

            # harmy = harm_1+harm

        if config.use_gan:
            with tf.variable_scope('Generator') as scope: 
                gen_op = modules.GAN_generator(harm)
        # with tf.variable_scope('Discriminator') as scope: 
        #     D_real = modules.GAN_discriminator(target_placeholder[:,:,:60],input_placeholder)
        #     scope.reuse_variables()
        #     D_fake = modules.GAN_discriminator(gen_op,input_placeholder)


        saver = tf.train.Saver(max_to_keep= config.max_models_to_keep)


        init_op = tf.group(tf.global_variables_initializer(), tf.local_variables_initializer())
        sess = tf.Session()

        sess.run(init_op)

        ckpt = tf.train.get_checkpoint_state(config.log_dir)

        if ckpt and ckpt.model_checkpoint_path:
            print("Using the model in %s"%ckpt.model_checkpoint_path)
            saver.restore(sess, ckpt.model_checkpoint_path)

        mix_stft = utils.file_to_stft(os.path.join(file_path,file_name), mode = mode)

        targs = utils.input_to_feats(os.path.join(file_path,file_name), mode = mode)

        # f0_sac = utils.file_to_sac(os.path.join(file_path,file_name))
        # f0_sac = (f0_sac-min_feat[-2])/(max_feat[-2]-min_feat[-2])

        in_batches, nchunks_in = utils.generate_overlapadd(mix_stft)
        in_batches = in_batches/max_mix
        # in_batches = utils.normalize(in_batches, 'mix_stft', mode=config.norm_mode_in)
        val_outer = []

        first_pred = []

        cleaner = []

        gan_op =[]

        for in_batch in in_batches:
            val_f0, val_vuv = sess.run([f0, vuv], feed_dict={input_placeholder: in_batch})
            if config.use_gan:
                val_op = sess.run(gen_op, feed_dict={input_placeholder: in_batch})
                
                gan_op.append(val_op)

            # first_pred.append(harm1)
            # cleaner.append(val_harm)
            # val_harm = val_harm
            val_outs = np.concatenate((val_f0, val_vuv), axis=-1)
            val_outer.append(val_outs)

        val_outer = np.array(val_outer)
        val_outer = utils.overlapadd(val_outer, nchunks_in)    
        val_outer[:,-1] = np.round(val_outer[:,-1])
        val_outer = val_outer[:targs.shape[0],:]
        val_outer = np.clip(val_outer,0.0,1.0)

        #Test purposes only
        # first_pred = np.array(first_pred)
        # first_pred = utils.overlapadd(first_pred, nchunks_in) 

        # cleaner = np.array(cleaner)
        # cleaner = utils.overlapadd(cleaner, nchunks_in) 

        if config.use_gan:
            gan_op = np.array(gan_op)
            gan_op = utils.overlapadd(gan_op, nchunks_in) 


        targs = (targs-min_feat)/(max_feat-min_feat)

        # import pdb;pdb.set_trace()

        # first_pred = (first_pred-min_feat[:60])/(max_feat[:60]-min_feat[:60])
        # cleaner = (cleaner-min_feat[:60])/(max_feat[:60]-min_feat[:60])


        

        if show_plots:

            # import pdb;pdb.set_trace()
    
            

            plt.figure(3)

            f0_output = val_outer[:,-2]*((max_feat[-2]-min_feat[-2])+min_feat[-2])
            f0_output = f0_output*(1-targs[:,-1])
            f0_output[f0_output == 0] = np.nan
            plt.plot(f0_output, label = "Predicted Value")
            f0_gt = targs[:,-2]*((max_feat[-2]-min_feat[-2])+min_feat[-2])
            f0_gt = f0_gt*(1-targs[:,-1])
            f0_gt[f0_gt == 0] = np.nan
            plt.plot(f0_gt, label="Ground Truth")
            f0_difference = np.nan_to_num(abs(f0_gt-f0_output))
            f0_greater = np.where(f0_difference>config.f0_threshold)
            diff_per = f0_greater[0].shape[0]/len(f0_output)
            plt.suptitle("Percentage correct = "+'{:.3%}'.format(1-diff_per))
            # import pdb;pdb.set_trace()


            # import pdb;pdb.set_trace()
            # uu = f0_sac[:,0]*(1-f0_sac[:,1])
            # uu[uu == 0] = np.nan
            # plt.plot(uu, label="Sac f0")
            plt.legend()
            plt.figure(4)
            ax1 = plt.subplot(211)
            plt.plot(val_outer[:,-1])
            ax1.set_title("Predicted Voiced/Unvoiced", fontsize = 10)
            ax2 = plt.subplot(212)
            plt.plot(targs[:,-1])
            ax2.set_title("Ground Truth Voiced/Unvoiced", fontsize = 10)
            plt.show()
        if save_file:
            
            val_outer = np.ascontiguousarray(val_outer*(max_feat-min_feat)+min_feat)
            targs = np.ascontiguousarray(targs*(max_feat-min_feat)+min_feat)

            # val_outer = np.ascontiguousarray(utils.denormalize(val_outer,'feats', mode=config.norm_mode_out))
            try:
                utils.feats_to_audio(val_outer,file_name[:-4]+'_synth_pred_f0')
                print("File saved to %s" % config.val_dir+file_name[:-4]+'_synth_pred_f0.wav')
            except:
                print("Couldn't synthesize with predicted f0")
            try:
                val_outer[:,-2:] = targs[:,-2:]
                utils.feats_to_audio(val_outer,file_name[:-4]+'_synth_ori_f0')
                print("File saved to %s" % config.val_dir+file_name[:-4]+'_synth_ori_f0.wav')
            except:
                print("Couldn't synthesize with original f0")
                




if __name__ == '__main__':
    if sys.argv[1] == '-train' or sys.argv[1] == '--train' or sys.argv[1] == '--t' or sys.argv[1] == '-t':
        print("Training")
        tf.app.run(main=train)
    elif sys.argv[1] == '-synth' or sys.argv[1] == '--synth' or sys.argv[1] == '--s' or sys.argv[1] == '-s':
        if len(sys.argv)<3:
            print("Please give a file to synthesize")
        else:
            file_name = sys.argv[2]
            if not file_name.endswith('.wav'):
                file_name = file_name+'.wav'
            print("Synthesizing File %s"% file_name)
            if '-p' in sys.argv or '--p' in sys.argv or '-plot' in sys.argv or '--plot' in sys.argv:
                
                if '-ns' in sys.argv or '--ns' in sys.argv or '-nosave' in sys.argv or '--nosave' in sys.argv:
                    print("Just showing plots for File %s"% sys.argv[2])
                    synth_file(file_name,show_plots=True, save_file=False)
                else:
                    print("Synthesizing File %s And Showing Plots"% sys.argv[2])
                    synth_file(file_name,show_plots=True, save_file=True)
            else:
                print("Synthesizing File %s, Not Showing Plots"% sys.argv[2])
                synth_file(file_name,show_plots=False, save_file=True)

    elif sys.argv[1] == '-help' or sys.argv[1] == '--help' or sys.argv[1] == '--h' or sys.argv[1] == '-h':
        print("%s --train to train the model"%sys.argv[0])
        print("%s --synth <filename> to synthesize file"%sys.argv[0])
        print("%s --synth <filename> -- plot to synthesize file and show plots"%sys.argv[0])
        print("%s --synth <filename> -- plot --ns to just show plots"%sys.argv[0])
    else:
        print("Unable to decipher inputs please use %s --help for help on how to use this function"%sys.argv[0])
  


