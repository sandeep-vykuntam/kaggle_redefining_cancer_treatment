import logging
import time
import tensorflow as tf
from tensorflow.python.framework.errors_impl import OutOfRangeError
from tensorflow.python.training.monitored_session import SingularMonitoredSession
from tensorflow.python.ops import variables as tf_variables
from src.task_spec import get_logs_path
from src.trainer import Trainer


class Evaluator(Trainer):
    """
    Default class for continuous evaluation in distributed training. This class extends modifies
    the default trainer to create its own session.
    """

    def __init__(self, checkpoints_dir, max_time=None, singular_monitored_session_config=None,
                 infinite_loop=True, dataset=None):
        """
        :param str checkpoints_dir: directory with the checkpoints, this should be the log_dir
        of the trainer
        :param int max_time: max time to run the training, by default isNone to run indefinitely
        :param tf.ConfigProto singular_monitored_session_config: an instance of tf.ConfigProto,
        the configuration for the singular monitored session
        :param bool infinite_loop: whether to run the evaluation in an infinite loop or not.
        Defaults to True
        :param TFDataSet dataset: the dataset for this evaluator
        """
        self.checkpoints_dir = get_logs_path(checkpoints_dir)
        self.max_time = max_time
        self.singular_monitored_session_config = singular_monitored_session_config
        self.infinite_loop = infinite_loop
        self.dataset = dataset
        self.lastest_checkpoint = None

    def run(self, batch_size=1, epochs=1):
        while True:
            with tf.Graph().as_default():
                logging.info('Creating graph...')
                if self.dataset is None:
                    dataset_tensor = None
                else:
                    dataset_tensor = self.dataset.read(batch_size=batch_size,
                                                       num_epochs=epochs,
                                                       shuffle=False)
                graph_data = self.create_graph(dataset_tensor, batch_size)
                self.saver = tf.train.Saver(var_list=tf_variables.trainable_variables())
                hooks = self.create_hooks(graph_data)
                hooks.append(self)
                with SingularMonitoredSession(hooks=hooks,
                                              config=self.singular_monitored_session_config) as sess:
                    logging.info('Starting evaluation...')
                    try:
                        while not sess.should_stop():
                            self.step(sess, graph_data)
                    except OutOfRangeError:
                        pass
            if not self.infinite_loop:
                break

    def after_create_session(self, session, coord):
        checkpoint = tf.train.latest_checkpoint(self.checkpoints_dir)
        # wait until a new check point is available
        while self.lastest_checkpoint == checkpoint:
            time.sleep(30)  # sleep 30 seconds waiting for a new checkpoint
            checkpoint = tf.train.latest_checkpoint(self.checkpoints_dir)
        logging.info('Restoring model from {}'.format(checkpoint))
        self.saver.restore(session, checkpoint)
        self.lastest_checkpoint = checkpoint

    def create_graph(self, dataset_tensor, batch_size):
        """
        Function to create the graph
        :param dataset_tensor: the tensor with the data created with the dataset.
        :param batch_size: the batch_size used when run() is called
        :return: Information related with the graph. It will be passed to other functions
        """
        raise NotImplementedError('Should have implemented this')

    def create_hooks(self, graph_data):
        """
        Creates the hooks for the session. This function is called after the graph is created and
        before the session is created.
        :param graph_data: the graph data returned create_graph
        :return: The list of hooks for the session.
        """
        return []

    def step(self, session, graph_data):
        """
        Function to run one time step.
        :param session: the session
        :param graph_data: the graph data returned in create_graph
        """
        raise NotImplementedError('Should have implemented this')