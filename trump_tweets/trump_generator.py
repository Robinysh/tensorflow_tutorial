""" A clean, no_frills character-level generative language model.

CS 20: "TensorFlow for Deep Learning Research"
cs20.stanford.edu
Danijar Hafner (mail@danijar.com)
& Chip Huyen (chiphuyen@cs.stanford.edu)
Lecture 11

Modified by Robin Yuen (robin.ysh@gmail.com)
"""
import os
os.environ['TF_CPP_MIN_LOG_LEVEL']='2'
import random
import sys
sys.path.append('..')
import time

import tensorflow as tf

def safe_mkdir(path):
    """ Create a directory if there isn't one already. """
    try:
        os.mkdir(path)
    except OSError:
        pass

def vocab_encode(text, vocab):
    return [vocab.index(x) for x in text if x in vocab]

def vocab_decode(array, vocab):
    return ''.join([vocab[x] if x>=0 else 'PAD' for x in array])

def read_data(filename, vocab, window, overlap):
    lines = [line.strip() for line in open(filename, 'r').readlines()]
    while True:
        random.shuffle(lines)

        for text in lines:
            text = vocab_encode(text, vocab)
            for start in range(0, len(text), overlap):
                chunk = text[start: start + window]
                chunk += [-1]*(window-len(chunk))
                yield chunk

def read_batch(stream, batch_size):
    batch = []
    for element in stream:
        batch.append(element)
        if len(batch) == batch_size:
            yield batch
            batch = []
    yield batch

class CharRNN(object):
    def __init__(self, model):
        self.model = model
        self.path = 'data/' + model + '.txt'
        self.vocab = (" $%'()+,-./123456790:;=?ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "'\"_abcdefghijklmnopqrstuvwxyz{|}@#➡📈")

        self.seq = tf.placeholder(tf.int32, [None, None])
        self.temp = tf.constant(.2)
        self.hidden_sizes = [128, 256]
        self.batch_size = 128
        self.lr = 0.0003
        self.skip_step = 50 # number of training per infer
        self.num_steps = 50 # number of chars for RNN unrolled
        self.len_generated = 200
        self.gstep = tf.Variable(0, dtype=tf.int32, trainable=False, name='global_step')

    def create_rnn(self, seq):
        layers = [tf.nn.rnn_cell.GRUCell(size) for size in self.hidden_sizes]
        cells = tf.nn.rnn_cell.MultiRNNCell(layers)
        batch = tf.shape(seq)[0]
        zero_states = cells.zero_state(batch, dtype=tf.float32)
        self.in_state = tuple([tf.placeholder_with_default(state, [None, state.shape[1]]) 
                                for state in zero_states])

        length = tf.reduce_sum(tf.reduce_max(seq, 2), 1)
        self.output, self.out_state = tf.nn.dynamic_rnn(cells, seq, length, self.in_state)

    def create_model(self):
        seq = tf.one_hot(self.seq, len(self.vocab))
        self.create_rnn(seq)
        self.logits = tf.layers.dense(self.output, len(self.vocab), None)
        loss = tf.nn.softmax_cross_entropy_with_logits(logits=self.logits[:, :-1], 
                                                        labels=seq[:, 1:])
        self.loss = tf.reduce_sum(loss)
        self.sample = tf.multinomial(self.logits[:, -1] / self.temp, 1)[:, 0] 
        #self.sample = tf.multinomial(tf.exp(self.logits[:, -1] / 1.5), 1)[:, 0] 
        self.opt = tf.train.AdamOptimizer(self.lr).minimize(self.loss, global_step=self.gstep)

    def train(self):
        saver = tf.train.Saver()
        start = time.time()
        min_loss = None
        with tf.Session() as sess:
            writer = tf.summary.FileWriter('graphs/gist', sess.graph)
            sess.run(tf.global_variables_initializer())
            
            ckpt = tf.train.get_checkpoint_state(os.path.dirname('checkpoints/' + self.model + '/checkpoint'))
            if ckpt and ckpt.model_checkpoint_path:
                saver.restore(sess, ckpt.model_checkpoint_path)
            
            iteration = self.gstep.eval()
            stream = read_data(self.path, self.vocab, self.num_steps, overlap=self.num_steps//2)
            data = read_batch(stream, self.batch_size)
            while True:
                batch = next(data)
                batch_loss, _ = sess.run([self.loss, self.opt], {self.seq: batch})
                if (iteration + 1) % self.skip_step == 0:
                    print('Iter {}. \n    Loss {}. Time {}'.format(iteration, batch_loss, time.time() - start))
                    self.online_infer(sess)
                    start = time.time()
                    checkpoint_name = 'checkpoints/' + self.model + '/char-rnn'
                    if min_loss is None:
                        saver.save(sess, checkpoint_name, iteration)
                    elif batch_loss < min_loss:
                        saver.save(sess, checkpoint_name, iteration)
                        min_loss = batch_loss
                iteration += 1

    def online_infer(self, sess):
        """ Generate sequence one character at a time, based on the previous character
        """
        for seed in ['Hillary', 'I', 'R', 'T', '@', 'N', 'M', '.', 'G', 'A', 'W']:
            sentence = seed
            state = None
            for _ in range(self.len_generated):
                batch = [vocab_encode(sentence[-1], self.vocab)]
                feed = {self.seq: batch}
                if state is not None: # for the first decoder step, the state is None
                    for i in range(len(state)):
                        feed.update({self.in_state[i]: state[i]})
                index, state = sess.run([self.sample, self.out_state], feed)
                sentence += vocab_decode(index, self.vocab)
            print('\t' + sentence)

def main():
    model = 'trump_tweets'
    safe_mkdir('checkpoints')
    safe_mkdir('checkpoints/' + model)

    lm = CharRNN(model)
    lm.create_model()
    lm.train()
    
if __name__ == '__main__':
    main()
