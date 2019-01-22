import tensorflow as tf
import numpy as np
import math
from visdom import Visdom
from tensorflow.contrib.layers.python.layers import batch_norm as batch_norm

LAYER1_SIZE = 512
LAYER2_SIZE = 512
LAYER3_SIZE = 512
LEARNING_RATE = 0.001
TAU = 0.001
L2 = 0.01
Plot = True

if Plot:
    vis = Visdom()
    x, y = 0, 0
    loss = vis.line(X=np.array([x]), Y=np.array([y]))


class CriticNetwork:
    def __init__(self, sess, state_dim, action_dim):
        self.time_step = 0
        self.sess = sess
        # create q network
        self.state_input, \
        self.action_input, \
        self.q_value_output, \
        self.net, \
        self.is_training = self.create_q_network(state_dim, action_dim)

        # create target q network (the same structure with q network)
        self.target_state_input, \
        self.target_action_input, \
        self.target_q_value_output, \
        self.target_update, \
        self.target_is_training = self.create_target_q_network(state_dim, action_dim, self.net)

        self.create_training_method()

        # initialization
        self.sess.run(tf.initialize_all_variables())

        self.update_target()
        self.load_network()

    def create_training_method(self):
        self.y_input = tf.placeholder("float", [None, 1])
        self.cost = tf.reduce_mean(tf.square(self.y_input - self.q_value_output))
        self.optimizer = tf.train.AdamOptimizer(LEARNING_RATE).minimize(self.cost)
        self.action_gradients = tf.gradients(self.q_value_output, self.action_input)

    def create_q_network(self, state_dim, action_dim):
        layer1_size = LAYER1_SIZE
        layer2_size = LAYER2_SIZE
        layer3_size = LAYER3_SIZE

        state_input = tf.placeholder("float", [None, state_dim])
        action_input = tf.placeholder("float", [None, action_dim])
        is_training = tf.placeholder(tf.bool)

        W1 = self.variable([state_dim, layer1_size], state_dim)
        b1 = self.variable([layer1_size], state_dim)
        W2 = self.variable([layer1_size, layer2_size], layer1_size + action_dim)
        W2_action = self.variable([action_dim, layer2_size], layer1_size + action_dim)
        b2 = self.variable([layer2_size], layer1_size + action_dim)
        W3 = self.variable([layer2_size, layer3_size], layer2_size)
        b3 = self.variable([layer3_size], layer2_size)
        W4 = tf.Variable(tf.random_uniform([layer3_size, 1], -3e-3, 3e-3))
        b4 = tf.Variable(tf.random_uniform([1], -3e-3, 3e-3))

        # layer0_bn = self.batch_norm_layer(state_input, training_phase=is_training, scope_bn='q_batch_norm_0',activation=tf.identity)
        layer1 = tf.matmul(state_input, W1) + b1
        layer1_bn = self.batch_norm_layer(layer1, training_phase=is_training, scope_bn='q_batch_norm_1',activation=tf.nn.relu)
        layer2 = tf.matmul(layer1_bn, W2) + tf.matmul(action_input, W2_action) + b2
        layer2_bn = self.batch_norm_layer(layer2, training_phase=is_training, scope_bn='q_batch_norm_2',activation=tf.nn.relu)
        layer3 = tf.matmul(layer2_bn, W3) + b3
        layer3_bn = self.batch_norm_layer(layer3, training_phase=is_training, scope_bn='q_batch_norm_3',activation=tf.nn.relu)
        q_value_output = tf.identity(tf.matmul(layer3_bn, W4) + b4)

        return state_input, action_input, q_value_output, [W1, b1, W2, W2_action, b2, W3, b3, W4, b4], is_training

    def create_target_q_network(self, state_dim, action_dim, net):
        state_input = tf.placeholder("float", [None, state_dim])
        action_input = tf.placeholder("float", [None, action_dim])
        is_training = tf.placeholder(tf.bool)

        ema = tf.train.ExponentialMovingAverage(decay=1 - TAU)
        target_update = ema.apply(net)
        target_net = [ema.average(x) for x in net]

        # layer0_bn = self.batch_norm_layer(state_input, training_phase=is_training, scope_bn='target_q_batch_norm_0',activation=tf.identity)
        layer1 = tf.matmul(state_input, target_net[0]) + target_net[1]
        layer1_bn = self.batch_norm_layer(layer1, training_phase=is_training, scope_bn='q_target_batch_norm_1',activation=tf.nn.relu)
        layer2 = tf.matmul(layer1_bn, target_net[2]) + tf.matmul(action_input, target_net[3]) + target_net[4]
        layer2_bn = self.batch_norm_layer(layer2, training_phase=is_training, scope_bn='q_target_batch_norm_2',activation=tf.nn.relu)
        layer3 = tf.matmul(layer2_bn, target_net[5]) + target_net[6]
        layer3_bn = self.batch_norm_layer(layer3, training_phase=is_training, scope_bn='q_target_batch_norm_3',activation=tf.nn.relu)
        q_value_output = tf.identity(tf.matmul(layer3_bn, target_net[7]) + target_net[8])

        return state_input, action_input, q_value_output, target_update, is_training

    def update_target(self):
        self.sess.run(self.target_update)

    def train(self, y_batch, state_batch, action_batch):
        self.time_step += 1
        self.sess.run(self.optimizer, feed_dict={
            self.y_input: y_batch,
            self.state_input: state_batch,
            self.action_input: action_batch,
            self.is_training: True
        })
        critic_loss = self.sess.run(self.cost, feed_dict={self.y_input: y_batch, self.state_input: state_batch,
                                                          self.action_input: action_batch, self.is_training: True})
        if Plot:
            vis.line(X=np.array([self.time_step]), Y=np.array([critic_loss]), win=loss, update='append', name='Loss')

    def gradients(self, state_batch, action_batch):
        return self.sess.run(self.action_gradients, feed_dict={
            self.state_input: state_batch,
            self.action_input: action_batch,
            self.is_training: False
        })[0]

    def target_q(self, state_batch, action_batch):
        return self.sess.run(self.target_q_value_output, feed_dict={
            self.target_state_input: state_batch,
            self.target_action_input: action_batch,
            self.target_is_training: False
        })

    def q_value(self, state_batch, action_batch):
        return self.sess.run(self.q_value_output, feed_dict={
            self.state_input: state_batch,
            self.action_input: action_batch,
            self.is_training: False})

    # f fan-in size
    def variable(self, shape, f):
        return tf.Variable(tf.random_uniform(shape, -1 / math.sqrt(f), 1 / math.sqrt(f)))

    def batch_norm_layer(self, x, training_phase, scope_bn, activation=None):
        return tf.cond(training_phase,
                       lambda: tf.contrib.layers.batch_norm(x, activation_fn=activation, center=True, scale=True,
                                                            updates_collections=None, is_training=True, reuse=None,
                                                            scope=scope_bn, decay=0.9, epsilon=1e-5),
                       lambda: tf.contrib.layers.batch_norm(x, activation_fn=activation, center=True, scale=True,
                                                            updates_collections=None, is_training=False, reuse=True,
                                                            scope=scope_bn, decay=0.9, epsilon=1e-5))

    def load_network(self):
        self.saver = tf.train.Saver()
        checkpoint = tf.train.get_checkpoint_state("saved_critic_networks")
        if checkpoint and checkpoint.model_checkpoint_path:
            self.saver.restore(self.sess, checkpoint.model_checkpoint_path)
            print("Successfully loaded:", checkpoint.model_checkpoint_path)
        else:
            print("Could not find old network weights")

    def save_network(self, time_step):
        print('save critic-network...', time_step)
        self.saver.save(self.sess, 'saved_critic_networks/' + 'critic-network', global_step=time_step)
