import openai
from openai.types.fine_tuning.job_create_params import Hyperparameters


client = openai.Client()

response = client.fine_tuning.jobs.create(
    training_file="file-TK98nyomKNQnivDBpesgtRzu",
    validation_file="file-IE8cqBdjro45ohCcBZIODfcP",
    model="gpt-3.5-turbo-0125",
    hyperparameters=Hyperparameters(
        n_epochs=1, batch_size=2, learning_rate_multiplier=0.5
    ),
)

print(response)
