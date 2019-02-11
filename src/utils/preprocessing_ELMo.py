from keras.preprocessing.sequence import pad_sequences
from keras.utils import np_utils
from utils import glove
from nlp import dictionary as dict
import logging
import numpy as np
import random
import tensorflow as tf
import tensorflow_hub as hub
from keras import backend as K


def prepare_sequential(train_doc, train_answer, test_doc, test_answer, val_doc, val_answer,
                       max_document_length=1000,
                       max_vocabulary_size=50000,
                       embeddings_size=50,
                       stem_test = False):
    """
        Prepares a dataset for use by a sequential, categorical model.

        :param train_doc: the training documents
        :param train_answer: the KPs for the training documents
        :param test_doc: the test documents
        :param test_answer: the KPs for the test documents
        :param val_doc: the validation documents (can be None)
        :param val_answer: the KPs for the validation documents (can be None)
        :param max_document_length: the maximum length of the documents (shorter documents will be truncated!)
        :param max_vocabulary_size: the maximum size of the vocabulary to use
        (i.e. we keep only the top max_vocabulary_size words)
        :param embeddings_size: the size of the GLoVE embeddings to use
        :param stem_test: set the value to True if the test set answers are stemmed
        :return: a tuple (train_x, train_y, test_x, test_y, val_x, val_y, embedding_matrix) containing the training,
        test and validation set, and an embedding matrix for an Embedding layer
        """

    # print(train_doc)  # gl

    train_answer_seq = make_sequential(train_doc, train_answer)

    if not stem_test:
        test_answer_seq = make_sequential(test_doc, test_answer)
    else:
        import copy
        stemmed_test_doc = copy.deepcopy(test_doc)
        stemmed_test_doc = stem_dataset(stemmed_test_doc)
        test_answer_seq = make_sequential(stemmed_test_doc,test_answer)

    # Prepare validation return data
    val_x = None
    val_y = None

    if val_doc and val_answer:
        val_answer_seq = make_sequential(val_doc, val_answer)

    # print(train_answer_seq)  # gl

    # Transform the documents to sequence
    documents_full = []
    train_y = []
    test_y = []

    if val_doc and val_answer:
        val_y = []

    for key, doc in train_doc.items():
        documents_full.append(token for token in doc)
        train_y.append(train_answer_seq[key])
    for key, doc in test_doc.items():
        documents_full.append(token for token in doc)
        test_y.append(test_answer_seq[key])

    if val_doc and val_answer:
        for key, doc in val_doc.items():
            documents_full.append(token for token in doc)
            val_y.append(val_answer_seq[key])

    logging.debug("Fitting dictionary on %s documents..." % len(documents_full))

    dictionary = dict.Dictionary(num_words=max_vocabulary_size)
    dictionary.fit_on_texts(documents_full)

    logging.debug("Dictionary fitting completed. Found %s unique tokens" % len(dictionary.word_index))

    print(train_doc)
    # Now we can prepare the actual input
    train_x = dictionary.texts_to_sequences(train_doc.values())
    test_x = dictionary.texts_to_sequences(test_doc.values())
    if val_doc and val_answer:
        val_x = dictionary.texts_to_sequences(val_doc.values())

    logging.debug("Longest training document : %s tokens" % len(max(train_x, key=len)))
    logging.debug("Longest test document :     %s tokens" % len(max(test_x, key=len)))
    if val_doc and val_answer:
        logging.debug("Longest validation document : %s tokens" % len(max(val_x, key=len)))

    train_x = np.asarray(pad_sequences(train_x, maxlen=max_document_length, padding='post', truncating='post'))
    train_y = pad_sequences(train_y, maxlen=max_document_length, padding='post', truncating='post')
    train_y = make_categorical(train_y)
    # print('preprocessing...')
    # print(train_x)  # gl
    test_x = np.asarray(pad_sequences(test_x, maxlen=max_document_length, padding='post', truncating='post'))
    test_y = pad_sequences(test_y, maxlen=max_document_length, padding='post', truncating='post')
    test_y = make_categorical(test_y)

    if val_doc and val_answer:
        val_x = np.asarray(pad_sequences(val_x, maxlen=max_document_length, padding='post', truncating='post'))
        val_y = pad_sequences(val_y, maxlen=max_document_length, padding='post', truncating='post')
        val_y = make_categorical(val_y)

    logging.debug("Training set samples size   : %s", np.shape(train_x))
    logging.debug("Training set answers size   : %s", np.shape(train_y))
    logging.debug("Test set samples size       : %s", np.shape(test_x))
    logging.debug("Test set answers size       : %s ", np.shape(test_y))

    if val_doc and val_answer:
        logging.debug("Validation set samples size : %s", np.shape(val_x))
        logging.debug("Validation set answers size : %s ", np.shape(val_y))

    # prepare the matrix for the embedding layer
    word_index = dictionary.word_index
    embeddings_index = glove.load_glove('', embeddings_size)

    num_words = min(max_vocabulary_size, 1 + len(word_index))

    logging.debug("Building embedding matrix of size [%s,%s]..." % (num_words, embeddings_size))

    embedding_matrix = np.zeros((num_words, embeddings_size))
    for word, i in word_index.items():
        if i >= num_words:
            continue
        embedding_vector = embeddings_index.get(word)
        if embedding_vector is not None:
            # words not found in embedding index will be all-zeros.
            embedding_matrix[i] = embedding_vector

    return train_x, train_y, test_x, test_y, val_x, val_y, embedding_matrix


def prepare_elmo_sequential(train_doc, train_answer, test_doc, test_answer, val_doc, val_answer,
                            max_document_length=1000,
                            max_vocabulary_size=50000,
                            embeddings_size=1024,
                            stem_test=False):
    """
        Prepares a dataset for use by a sequential, categorical model.

        :param train_doc: the training documents
        :param train_answer: the KPs for the training documents
        :param test_doc: the test documents
        :param test_answer: the KPs for the test documents
        :param val_doc: the validation documents (can be None)
        :param val_answer: the KPs for the validation documents (can be None)
        :param max_document_length: the maximum length of the documents (shorter documents will be truncated!)
        :param max_vocabulary_size: the maximum size of the vocabulary to use
        (i.e. we keep only the top max_vocabulary_size words)
        :param embeddings_size: the size of the GLoVE embeddings to use
        :param stem_test: set the value to True if the test set answers are stemmed
        :return: a tuple (train_x, train_y, test_x, test_y, val_x, val_y, embedding_matrix) containing the training,
        test and validation set, and an embedding matrix for an Embedding layer
        """

    # print(train_doc)  # gl

    train_answer_seq = make_sequential(train_doc, train_answer)

    if not stem_test:
        test_answer_seq = make_sequential(test_doc, test_answer)
    else:
        import copy
        stemmed_test_doc = copy.deepcopy(test_doc)
        stemmed_test_doc = stem_dataset(stemmed_test_doc)
        test_answer_seq = make_sequential(stemmed_test_doc,test_answer)

    # Prepare validation return data
    val_x = None
    val_y = None

    if val_doc and val_answer:
        val_answer_seq = make_sequential(val_doc, val_answer)

    # print(train_answer_seq)  # gl

    # Transform the documents to sequence
    documents_full = []
    train_y = []
    test_y = []

    if val_doc and val_answer:
        val_y = []

    for key, doc in train_doc.items():
        documents_full.append(token for token in doc)
        train_y.append(train_answer_seq[key])
    for key, doc in test_doc.items():
        documents_full.append(token for token in doc)
        test_y.append(test_answer_seq[key])

    if val_doc and val_answer:
        for key, doc in val_doc.items():
            documents_full.append(token for token in doc)
            val_y.append(val_answer_seq[key])

    logging.debug("Fitting dictionary on %s documents..." % len(documents_full))

    dictionary = dict.Dictionary(num_words=max_vocabulary_size)
    dictionary.fit_on_texts(documents_full)

    logging.debug("Dictionary fitting completed. Found %s unique tokens" % len(dictionary.word_index))

    print(train_doc)  # gl: train_doc is still strings; list of documents with tokenized content

    # Now we can prepare the actual input
    train_x = dictionary.texts_to_sequences(train_doc.values())
    test_x = dictionary.texts_to_sequences(test_doc.values())
    if val_doc and val_answer:
        val_x = dictionary.texts_to_sequences(val_doc.values())

    logging.debug("Longest training document : %s tokens" % len(max(train_x, key=len)))
    logging.debug("Longest test document :     %s tokens" % len(max(test_x, key=len)))
    if val_doc and val_answer:
        logging.debug("Longest validation document : %s tokens" % len(max(val_x, key=len)))

    train_x = np.asarray(pad_sequences(train_x, maxlen=max_document_length, padding='post', truncating='post'))
    train_y = pad_sequences(train_y, maxlen=max_document_length, padding='post', truncating='post')
    train_y = make_categorical(train_y)
    # print('preprocessing...')
    # print(train_x)  # gl
    test_x = np.asarray(pad_sequences(test_x, maxlen=max_document_length, padding='post', truncating='post'))
    test_y = pad_sequences(test_y, maxlen=max_document_length, padding='post', truncating='post')
    test_y = make_categorical(test_y)

    if val_doc and val_answer:
        val_x = np.asarray(pad_sequences(val_x, maxlen=max_document_length, padding='post', truncating='post'))
        val_y = pad_sequences(val_y, maxlen=max_document_length, padding='post', truncating='post')
        val_y = make_categorical(val_y)

    logging.debug("Training set samples size   : %s", np.shape(train_x))
    logging.debug("Training set answers size   : %s", np.shape(train_y))
    logging.debug("Test set samples size       : %s", np.shape(test_x))
    logging.debug("Test set answers size       : %s ", np.shape(test_y))

    if val_doc and val_answer:
        logging.debug("Validation set samples size : %s", np.shape(val_x))
        logging.debug("Validation set answers size : %s ", np.shape(val_y))

    logging.info("Initialize tensorflow session")
    # Initialize session
    sess = tf.Session()
    K.set_session(sess)

    elmo = hub.Module("https://tfhub.dev/google/elmo/2", trainable=True)
    sess.run(tf.global_variables_initializer())
    sess.run(tf.tables_initializer())

    # prepare the matrix for the embedding layer
    word_index = dictionary.word_index
    print(word_index)
    # embeddings_index = glove.load_glove('', embeddings_size)

    num_words = min(max_vocabulary_size, 1 + len(word_index))

    logging.debug("Building embedding matrix of size [%s,%s]..." % (num_words, embeddings_size))

    embedding_matrix = np.zeros((num_words, embeddings_size))
    for word, i in word_index.items():
        if i >= num_words:
            continue
        # embedding_vector = embeddings_index.get(word)
        # embedding_tensor = elmo([word], as_dict=True)["default"]
        embedding_tensor = elmo([word])
        embedding_vector = sess.run(embedding_tensor)
        print(embedding_vector)
        print(embedding_vector[0])
        print(embedding_tensor)
        print(embedding_tensor[0])
        print(word)
        print(i)
        if embedding_vector is not None:
            # words not found in embedding index will be all-zeros.
            embedding_matrix[i] = embedding_vector[0]

    return train_x, train_y, test_x, test_y, val_x, val_y, embedding_matrix


def make_sequential(documents, answers):
    """
    Transform an answer-based dataset (i.e. with a list of
    documents and a list of keyphrases) to a sequential, ner-like
    dataset, i.e. where the answer set for each document is composed
    by the lists of the documents' tokens marked as non-keyphrase (0),
    beginning of keyphrase (1) and inside-keyphrase (2).

    For example, for the tokens

    "I am a python developer since today."

    If the keyphrases are "python developer" and "today"" the answer
    set for these tokens is

    "[0 0 0 1 2 0 1]"

    :param documents: the list of documents
    :param answers: the list of keyphrases
    :return: the new answer set
    """

    seq_answers = {}

    for key, document in documents.items():
        doc_answers_set = answers[key]
        # Sort by length of the keyphrase. We process shorter KPs first so
        # that if they are contained by a longer KP we'll simply overwrite
        # the shorter one with the longer one
        doc_answers_set.sort(key=lambda a: len(a))

        # This field will contain the answer.
        # We initialize it as a list of zeros and we will fill it
        # with 1s and 2s later
        doc_answers_seq = [0] * len(document)

        for answer in doc_answers_set:
            # Find where the first word the KP appears
            appearances = [i for i, word in enumerate(document) if word == answer[0]]
            for idx in appearances:
                is_kp = True
                # Check if the KP matches also from its second word on
                for i in range(1, len(answer)):

                    if (i + idx) < len(document):
                        is_kp = answer[i] == document[i + idx]
                    else:
                        # We reached the end of the document
                        is_kp = False

                # If we found an actual KP, mark the tokens in the output list.
                if is_kp:
                    doc_answers_seq[idx] = 1
                    for i in range(1, len(answer)):
                        doc_answers_seq[idx + i] = 2

                        # for
        # for

        seq_answers[key] = doc_answers_seq

    return seq_answers


def make_categorical(x):
    """
    Transform a two-dimensional list into a 3-dimensional array. The 2nd
    dimension of the input list becomes a one-hot 2D array, e.g.
    if the input is [[1,2,0],...], the output will be
    [[[0,1,0],[0,0,1],[1,0,0]],...]

    :param x: a 2D-list
    :return: a 3D-numpy array
    """

    # How many categories do we have?
    num_categories = max([item for sublist in x for item in sublist]) + 1

    # Prepare numpy output
    new_x = np.zeros((len(x), len(x[0]), num_categories))

    # Use keras to make actual categorical transformation
    i = 0
    for doc in x:
        new_doc = np_utils.to_categorical(doc, num_classes=num_categories)
        new_x[i] = new_doc
        i += 1

    return new_x


def stem_dataset(dataset):

    from nltk.stem import PorterStemmer
    stemmer = PorterStemmer()

    for key, tokens in dataset.items():
        stemmed_tokens = [stemmer.stem(token) for token in tokens]
        dataset[key] = stemmed_tokens

    return dataset
