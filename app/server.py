from fastapi import FastAPI
from pydantic import BaseModel
from loguru import logger
import joblib

from sentence_transformers import SentenceTransformer
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline

import time
from datetime import datetime
import json

GLOBAL_CONFIG = {
    "model": {
        "featurizer": {
            "sentence_transformer_model": "all-mpnet-base-v2",
            "sentence_transformer_embedding_dim": 768
        },
        "classifier": {
            "serialized_model_path": "../data/news_classifier.joblib"
        }
    },
    "service": {
        "log_destination": "../data/logs.out"
    }
}

class PredictRequest(BaseModel):
    source: str
    url: str
    title: str
    description: str


class PredictResponse(BaseModel):
    scores: dict
    label: str


class TransformerFeaturizer(BaseEstimator, TransformerMixin):
    def __init__(self, dim, sentence_transformer_model):
        self.dim = dim
        self.sentence_transformer_model = sentence_transformer_model

    #estimator. Since we don't have to learn anything in the featurizer, this is a no-op
    def fit(self, X, y=None):
        return self

    #transformation: return the encoding of the document as returned by the transformer model
    def transform(self, X, y=None):
        return self.sentence_transformer_model.encode(X, normalize_embeddings=True)

class NewsCategoryClassifier:
    def __init__(self, config: dict) -> None:
        self.config = config
        """
        [TO BE IMPLEMENTED]
        1. Load the sentence transformer model and initialize the `featurizer` of type `TransformerFeaturizer` (Hint: revisit Week 1 Step 4)
        2. Load the serialized model as defined in GLOBAL_CONFIG['model'] into memory and initialize `model`
        """
        sentence_transfomer = SentenceTransformer('sentence-transformers/{model}'.format(
            model=GLOBAL_CONFIG['model']['featurizer']["sentence_transformer_model"]))
        dim = GLOBAL_CONFIG['model']['featurizer']["sentence_transformer_embedding_dim"]
        featurizer = TransformerFeaturizer(dim, sentence_transfomer)
        model = joblib.load(GLOBAL_CONFIG['model']['classifier']["serialized_model_path"])
        self.classes = model.classes_
        self.pipeline = Pipeline([
            ('transformer_featurizer', featurizer),
            ('classifier', model)
        ])

    def predict_proba(self, model_input: dict) -> dict:
        """
        [TO BE IMPLEMENTED]
        Using the `self.pipeline` constructed during initialization, 
        run model inference on a given model input, and return the 
        model prediction probability scores across all labels
        Output format: 
        {
            "label_1": model_score_label_1,
            "label_2": model_score_label_2 
            ...
        }
        """

        result = self.pipeline.predict_proba([model_input.description]).flatten()
        classes = self.classes
        return dict(zip(classes, result))

    def predict_label(self, model_input: dict) -> str:
        """
        [TO BE IMPLEMENTED]
        Using the `self.pipeline` constructed during initialization,
        run model inference on a given model input, and return the
        model prediction label
        Output format: predicted label for the model input
        """
        return self.pipeline.predict([model_input.description])


app = FastAPI()

@app.on_event("startup")
def startup_event():
    """
        [TO BE IMPLEMENTED]
        2. Initialize the `NewsCategoryClassifier` instance to make predictions online. You should pass any relevant config parameters from `GLOBAL_CONFIG` that are needed by NewsCategoryClassifier 
        3. Open an output file to write logs, at the destimation specififed by GLOBAL_CONFIG['service']['log_destination']
        
        Access to the model instance and log file will be needed in /predict endpoint, make sure you
        store them as global variables
    """
    global log_file
    global classifier
    classifier = NewsCategoryClassifier(GLOBAL_CONFIG)
    log_file = open(GLOBAL_CONFIG["service"]["log_destination"], "a")

    logger.info("Setup completed")


@app.on_event("shutdown")
def shutdown_event():
    # clean up
    """
        [TO BE IMPLEMENTED]
        1. Make sure to flush the log file and close any file pointers to avoid corruption
        2. Any other cleanups
    """
    log_file.close()
    logger.info("Shutting down application")


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    # get model prediction for the input request
    # construct the data to be logged
    # construct response
    """
        [TO BE IMPLEMENTED]
        1. run model inference and get model predictions for model inputs specified in `request`
        2. Log the following data to the log file (the data should be logged to the file that was opened in `startup_event`, and writes to the path defined in GLOBAL_CONFIG['service']['log_destination'])
        {
            'timestamp': <YYYY:MM:DD HH:MM:SS> format, when the request was received,
            'request': dictionary representation of the input request,
            'prediction': dictionary representation of the response,
            'latency': time it took to serve the request, in millisec
        }
        3. Construct an instance of `PredictResponse` and return
    """
    # Inference
    t0 = time.time()
    probs = classifier.predict_proba(request)
    pred = classifier.predict_label(request)[0]
    t1 = time.time()
    inference_time = t1 - t0

    # Logging
    log_info = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "request": request.dict(),
        "prediction": {'label': pred, 'scores':probs},
        "latency": inference_time,
    }
    log_file.write(f"{json.dumps(log_info)}\n")
    log_file.flush()
    return PredictResponse(scores=probs, label=pred)


@app.get("/")
def read_root():
    return {"Hello": "World"}

if __name__ == '__main__':
    test = NewsCategoryClassifier(GLOBAL_CONFIG)
    input_test = {
      "source": "<value>",
      "url": "<value>",
      "title": "<value>",
      "description": "This is a test phrase about Football and Voleyball."
    }
    print(test.predict_proba(input_test))

    print(test.predict_label(input_test))
