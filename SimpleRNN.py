from keras.layers import Bidirectional,Dense,Dropout,Embedding,LSTM,TimeDistributed
from keras.models import Sequential, load_model
from keras import regularizers
from data.datasets import Hulth
from eval import keras_metrics, metrics
from utils import info, preprocessing, postprocessing, plots
import logging
import numpy as np
import os

# LOGGING CONFIGURATION

logging.basicConfig(
    format='%(asctime)s\t%(levelname)s\t%(message)s',
    level=logging.DEBUG)

info.log_versions()

# END LOGGING CONFIGURATION

# GLOBAL VARIABLES

SAVE_MODEL = False
MODEL_PATH = "models/simplernn.h5"
SHOW_PLOTS = True

# END GLOBAL VARIABLES

# PARAMETERS for networks, tokenizers, etc...

FILTER = '!"#$%&()*+/:<=>?@[\\]^_`{|}~\t\n'
MAX_DOCUMENT_LENGTH = 550
MAX_VOCABULARY_SIZE = 20000
EMBEDDINGS_SIZE = 300
BATCH_SIZE = 32
EPOCHS = 10

# END PARAMETERS

logging.info("Loading dataset...")

data = Hulth("data/Hulth2003")

train_doc, train_answer = data.load_train()
test_doc, test_answer = data.load_test()
val_doc, val_answer = data.load_validation()

# Sanity check
# logging.info("Sanity check: %s",metrics.precision(test_answer,test_answer))

logging.info("Dataset loaded. Preprocessing data...")

train_x,train_y,test_x,test_y,val_x,val_y,embedding_matrix = preprocessing.\
    prepare_sequential(train_doc, train_answer, test_doc, test_answer,val_doc,val_answer,
                       tokenizer_filter=FILTER,
                       max_document_length=MAX_DOCUMENT_LENGTH,
                       max_vocabulary_size=MAX_VOCABULARY_SIZE,
                       embeddings_size=EMBEDDINGS_SIZE)

logging.info("Maximum possible recall: %s",
             metrics.recall(test_answer,
                               postprocessing.get_words(test_doc,postprocessing.undo_sequential(test_x, test_y))))

# weigh training examples: everything that's not class 0 (not kp)
# gets a heavier score
train_y_weights = np.argmax(train_y,axis=2) # this removes the one-hot representation
train_y_weights[train_y_weights > 0] = 10
train_y_weights[train_y_weights < 1] = 1

logging.info("Data preprocessing complete.")

if not SAVE_MODEL or not os.path.isfile(MODEL_PATH) :

    logging.debug("Building the network...")
    model = Sequential()

    embedding_layer = Embedding(np.shape(embedding_matrix)[0],
                                EMBEDDINGS_SIZE,
                                weights=[embedding_matrix],
                                input_length=MAX_DOCUMENT_LENGTH,
                                trainable=False)

    model.add(embedding_layer)
    model.add(Bidirectional(LSTM(500,activation='tanh', recurrent_activation='hard_sigmoid', return_sequences=True)))
    model.add(Dropout(0.25))
    model.add(TimeDistributed(Dense(200, activation='relu',kernel_regularizer=regularizers.l2(0.01))))
    model.add(Dropout(0.25))
    model.add(TimeDistributed(Dense(3, activation='softmax')))

    logging.info("Compiling the network...")
    model.compile(loss='categorical_crossentropy', optimizer='rmsprop', metrics=['accuracy'],
                  sample_weight_mode="temporal")
    print(model.summary())

    metrics_callback = keras_metrics.MetricsCallback(val_x,val_y)

    logging.info("Fitting the network...")
    history = model.fit(train_x, train_y,
                        validation_data=(val_x,val_y),
                        epochs=EPOCHS,
                        batch_size=BATCH_SIZE,
                        sample_weight=train_y_weights,
                        callbacks=[metrics_callback])

    if SHOW_PLOTS :
        plots.plot_accuracy(history)
        plots.plot_loss(history)
        plots.plot_prf(metrics_callback)

    if SAVE_MODEL :
        model.save(MODEL_PATH)
        logging.info("Model saved in %s", MODEL_PATH)

else :
    logging.info("Loading existing model from %s...",MODEL_PATH)
    model = load_model(MODEL_PATH)
    logging.info("Completed loading model from file")


logging.info("Predicting on test set...")
output = model.predict(x=test_x, verbose=1)
logging.debug("Shape of output array: %s",np.shape(output))

obtained_tokens = postprocessing.undo_sequential(train_x,output)
obtained_words = postprocessing.get_words(test_doc,obtained_tokens)

precision = metrics.precision(test_answer,obtained_words)
recall = metrics.recall(test_answer,obtained_words)
f1 = metrics.f1(precision,recall)

print("###    Obtained Scores    ###")
print("###     (full dataset)    ###")
print("###")
print("### Precision : %.4f" % precision)
print("### Recall    : %.4f" % recall)
print("### F1        : %.4f" % f1)
print("###                       ###")

keras_precision = keras_metrics.keras_precision(test_y,output)
keras_recall = keras_metrics.keras_recall(test_y,output)
keras_f1 = keras_metrics.keras_f1(test_y,output)

print("###    Obtained Scores    ###")
print("###    (fixed dataset)    ###")
print("###")
print("### Precision : %.4f" % keras_precision)
print("### Recall    : %.4f" % keras_recall)
print("### F1        : %.4f" % keras_f1)
print("###                       ###")
